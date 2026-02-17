import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from meetings.models import Meeting, Speaker
from transcription.models import Transcript, TranscriptSegment
from ai_copilot.models import CopilotSuggestion, CopilotRun, SpeakerUserMap
from ai_copilot.services.llm_gateway import llm_gateway, LLMGatewayError
from ai_copilot.services.validator import CopilotValidator, CopilotDeduplicator
from accounts.models import User

logger = logging.getLogger(__name__)


class CopilotOrchestrator:
    """
    Main orchestrator for Copilot functionality.
    Handles real-time incremental processing and post-meeting analysis.
    """
    
    # Configuration constants
    REALTIME_INTERVAL_SECONDS = 20  # Run every 20 seconds during live sessions
    REALTIME_SEGMENT_COUNT = 50    # Or every 50 segments, whichever comes first
    POST_MEETING_BATCH_SIZE = 100   # Process in batches of 100 segments
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def handle_final_transcript_segment(self, meeting_id: str, segment_id: str) -> None:
        """
        Handle a final transcript segment for real-time processing.
        Called whenever a transcript segment is finalized.
        
        Args:
            meeting_id: Meeting ID
            segment_id: Segment ID that was finalized
        """
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            
            # Check if meeting has active live session
            if not meeting.live_sessions.filter(status='active').exists():
                return
            
            # Get recent segments for incremental processing
            recent_segments = self._get_recent_segments(meeting, limit=self.REALTIME_SEGMENT_COUNT)
            
            if len(recent_segments) >= 10:  # Minimum segments for processing
                self._run_incremental_analysis(meeting, recent_segments)
                
        except Exception as e:
            logger.error(f"Error handling final segment for meeting {meeting_id}: {str(e)}")
    
    def run_post_meeting_analysis(self, meeting_id: str) -> CopilotRun:
        """
        Run complete post-meeting analysis.
        
        Args:
            meeting_id: Meeting ID
            
        Returns:
            CopilotRun object for tracking
        """
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            
            # Create run record
            run = CopilotRun.objects.create(
                meeting=meeting,
                mode=CopilotRun.RunMode.POST_MEETING,
                provider=llm_gateway.provider,
                model=llm_gateway.model,
                status=CopilotRun.RunStatus.STARTED
            )
            
            # Get all final segments
            all_segments = self._get_all_final_segments(meeting)
            run.segment_count = len(all_segments)
            run.save()
            
            if not all_segments:
                run.status = CopilotRun.RunStatus.FAILED
                run.error_message = "No transcript segments available"
                run.finished_at = timezone.now()
                run.save()
                return run
            
            # Prepare meeting context
            meeting_context = self._build_meeting_context(meeting)
            
            # Get existing items to avoid duplicates
            existing_items = self._get_existing_items_for_deduplication(meeting)
            
            # Run LLM analysis
            try:
                output = llm_gateway.generate_copilot_output(
                    transcript_window=all_segments,
                    meeting_context=meeting_context,
                    language=meeting.language_preference,
                    existing_items=existing_items
                )
                
                # Update run with token counts
                if 'metadata' in output:
                    run.input_token_count = output['metadata'].get('input_tokens', 0)
                    run.output_token_count = output['metadata'].get('output_tokens', 0)
                    run.processing_time_ms = output['metadata'].get('processing_time_ms', 0)
                
                # Validate and process output
                validated_output = CopilotValidator.validate_output(output)
                
                # Create suggestions (with deduplication)
                suggestions = CopilotDeduplicator.merge_or_create_suggestions(
                    meeting, validated_output, run
                )
                
                run.suggestion_count = len(suggestions)
                run.status = CopilotRun.RunStatus.SUCCESS
                run.finished_at = timezone.now()
                run.save()
                
                # Broadcast to clients
                self._broadcast_suggestions_update(meeting, suggestions)
                
                logger.info(f"Post-meeting analysis completed for {meeting.title}: {len(suggestions)} suggestions")
                
                return run
                
            except LLMGatewayError as e:
                run.status = CopilotRun.RunStatus.FAILED
                run.error_message = str(e)
                run.finished_at = timezone.now()
                run.save()
                
                logger.error(f"LLM error in post-meeting analysis for {meeting.title}: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error in post-meeting analysis for meeting {meeting_id}: {str(e)}")
            raise
    
    def _run_incremental_analysis(self, meeting: Meeting, segments: List[TranscriptSegment]) -> None:
        """
        Run incremental analysis for real-time processing.
        
        Args:
            meeting: Meeting object
            segments: Recent transcript segments
        """
        try:
            # Create run record
            run = CopilotRun.objects.create(
                meeting=meeting,
                mode=CopilotRun.RunMode.REALTIME_INCREMENTAL,
                provider=llm_gateway.provider,
                model=llm_gateway.model,
                status=CopilotRun.RunStatus.STARTED,
                segment_count=len(segments)
            )
            
            # Prepare meeting context
            meeting_context = self._build_meeting_context(meeting)
            
            # Get existing items to avoid duplicates
            existing_items = self._get_existing_items_for_deduplication(meeting)
            
            # Convert segments to dict format
            segments_dict = [self._segment_to_dict(seg) for seg in segments]
            
            # Run LLM analysis
            try:
                output = llm_gateway.generate_copilot_output(
                    transcript_window=segments_dict,
                    meeting_context=meeting_context,
                    language=meeting.language_preference,
                    existing_items=existing_items
                )
                
                # Validate and process output
                validated_output = CopilotValidator.validate_output(output)
                
                # Create suggestions (with deduplication)
                suggestions = CopilotDeduplicator.merge_or_create_suggestions(
                    meeting, validated_output, run
                )
                
                # Update run
                run.suggestion_count = len(suggestions)
                run.status = CopilotRun.RunStatus.SUCCESS
                run.finished_at = timezone.now()
                run.save()
                
                # Broadcast new suggestions to clients
                self._broadcast_suggestions_update(meeting, suggestions)
                
                logger.info(f"Incremental analysis completed for {meeting.title}: {len(suggestions)} new suggestions")
                
            except LLMGatewayError as e:
                run.status = CopilotRun.RunStatus.FAILED
                run.error_message = str(e)
                run.finished_at = timezone.now()
                run.save()
                
                logger.error(f"LLM error in incremental analysis for {meeting.title}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in incremental analysis for {meeting.title}: {str(e)}")
    
    def _get_recent_segments(self, meeting: Meeting, limit: int = 50) -> List[TranscriptSegment]:
        """
        Get recent final transcript segments for incremental processing.
        
        Args:
            meeting: Meeting object
            limit: Maximum number of segments to retrieve
            
        Returns:
            List of recent segments
        """
        # Get the most recent final segments
        segments = TranscriptSegment.objects.filter(
            transcript__meeting=meeting,
            is_final=True
        ).order_by('-created_at')[:limit]
        
        # Return in chronological order
        return list(reversed(segments))
    
    def _get_all_final_segments(self, meeting: Meeting) -> List[Dict[str, Any]]:
        """
        Get all final transcript segments for post-meeting analysis.
        
        Args:
            meeting: Meeting object
            
        Returns:
            List of segments in dict format
        """
        segments = TranscriptSegment.objects.filter(
            transcript__meeting=meeting,
            is_final=True
        ).order_by('start_ms')
        
        return [self._segment_to_dict(seg) for seg in segments]
    
    def _segment_to_dict(self, segment: TranscriptSegment) -> Dict[str, Any]:
        """
        Convert transcript segment to dictionary format for LLM.
        
        Args:
            segment: TranscriptSegment object
            
        Returns:
            Segment dictionary
        """
        return {
            'id': str(segment.id),
            'start_ms': segment.start_ms,
            'end_ms': segment.end_ms,
            'speaker_label': segment.speaker_label_raw,
            'speaker_display_name': segment.speaker.display_name if segment.speaker else None,
            'text': segment.text,
            'confidence': segment.confidence,
            'created_at': segment.created_at.isoformat()
        }
    
    def _build_meeting_context(self, meeting: Meeting) -> Dict[str, Any]:
        """
        Build meeting context for LLM prompt.
        
        Args:
            meeting: Meeting object
            
        Returns:
            Meeting context dictionary
        """
        # Get speaker mappings
        speaker_mappings = SpeakerUserMap.objects.filter(meeting=meeting)
        participants = []
        
        for mapping in speaker_mappings:
            participants.append(f"{mapping.speaker.label} → {mapping.user.email}")
        
        # Get existing accepted suggestions
        existing_suggestions = CopilotSuggestion.objects.filter(
            meeting=meeting,
            status=CopilotSuggestion.SuggestionStatus.ACCEPTED
        )
        
        return {
            'title': meeting.title,
            'description': meeting.description or '',
            'language': meeting.language_preference,
            'participants': participants,
            'speaker_count': meeting.speakers.count(),
            'existing_suggestions_count': existing_suggestions.count(),
            'meeting_time': meeting.created_at.isoformat() if meeting.created_at else None
        }
    
    def _get_existing_items_for_deduplication(self, meeting: Meeting) -> List[Dict[str, Any]]:
        """
        Get existing items for deduplication.
        
        Args:
            meeting: Meeting object
            
        Returns:
            List of existing items
        """
        existing_items = []
        
        # Get accepted suggestions
        suggestions = CopilotSuggestion.objects.filter(
            meeting=meeting,
            status=CopilotSuggestion.SuggestionStatus.ACCEPTED
        )
        
        for suggestion in suggestions:
            item = suggestion.payload_json.copy()
            item['type'] = suggestion.type
            item['dedupe_key'] = suggestion.dedupe_key
            existing_items.append(item)
        
        return existing_items
    
    def _broadcast_suggestions_update(self, meeting: Meeting, suggestions: List[CopilotSuggestion]) -> None:
        """
        Broadcast suggestions update to WebSocket clients.
        
        Args:
            meeting: Meeting object
            suggestions: List of suggestions
        """
        try:
            # Convert suggestions to dict format
            suggestions_dict = []
            for suggestion in suggestions:
                suggestion_dict = {
                    'id': str(suggestion.id),
                    'type': suggestion.type,
                    'status': suggestion.status,
                    'payload': suggestion.payload_json,
                    'confidence': suggestion.confidence,
                    'created_at': suggestion.created_at.isoformat()
                }
                suggestions_dict.append(suggestion_dict)
            
            # Send WebSocket message
            async_to_sync(self.channel_layer.group_send)(
                f"meeting_{meeting.id}",
                {
                    'type': 'copilot_suggestions_updated',
                    'data': {
                        'suggestions': suggestions_dict,
                        'meeting_id': str(meeting.id)
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error broadcasting suggestions update for {meeting.title}: {str(e)}")
    
    def accept_suggestion(self, suggestion_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Accept a Copilot suggestion and create the corresponding entity.
        
        Args:
            suggestion_id: Suggestion ID
            user_id: User ID accepting the suggestion
            
        Returns:
            Created entity data or None if failed
        """
        try:
            with transaction.atomic():
                suggestion = CopilotSuggestion.objects.select_for_update().get(id=suggestion_id)
                
                if suggestion.status != CopilotSuggestion.SuggestionStatus.PROPOSED:
                    raise ValueError("Suggestion is not in proposed status")
                
                # Create entity based on type
                if suggestion.type == CopilotSuggestion.SuggestionType.ACTION_ITEM:
                    entity_data = self._create_action_item_from_suggestion(suggestion, user_id)
                elif suggestion.type == CopilotSuggestion.SuggestionType.DECISION:
                    entity_data = self._create_decision_from_suggestion(suggestion, user_id)
                elif suggestion.type == CopilotSuggestion.SuggestionType.RISK:
                    entity_data = self._create_risk_from_suggestion(suggestion, user_id)
                elif suggestion.type == CopilotSuggestion.SuggestionType.QUESTION:
                    entity_data = self._create_question_from_suggestion(suggestion, user_id)
                else:
                    raise ValueError(f"Unknown suggestion type: {suggestion.type}")
                
                # Update suggestion status
                suggestion.status = CopilotSuggestion.SuggestionStatus.ACCEPTED
                suggestion.save()
                
                # Broadcast update
                self._broadcast_suggestion_status_update(suggestion)
                
                return entity_data
                
        except Exception as e:
            logger.error(f"Error accepting suggestion {suggestion_id}: {str(e)}")
            raise
    
    def _create_action_item_from_suggestion(self, suggestion: CopilotSuggestion, user_id: str) -> Dict[str, Any]:
        """Create action item from suggestion"""
        from transcription.models import ActionItem, Minutes
        
        payload = suggestion.payload_json
        
        # Find or create minutes
        minutes, _ = Minutes.objects.get_or_create(
            meeting=suggestion.meeting,
            defaults={'transcript': suggestion.meeting.transcripts.first()}
        )
        
        # Find assignee user
        assignee = None
        assignee_info = payload.get('assignee', {})
        if assignee_info.get('user_id'):
            try:
                assignee = User.objects.get(id=assignee_info['user_id'])
            except User.DoesNotExist:
                pass
        
        # Create action item
        action_item = ActionItem.objects.create(
            meeting=suggestion.meeting,
            minutes=minutes,
            title=payload['title'],
            description=payload['description'],
            assignee=assignee,
            due_date=payload.get('due_date'),
            priority=payload.get('priority', ActionItem.Priority.MEDIUM),
            source_segment_ids=suggestion.source_segment_ids
        )
        
        # Link to suggestion
        suggestion.accepted_action_item = action_item
        suggestion.save()
        
        return {
            'type': 'action_item',
            'id': str(action_item.id),
            'title': action_item.title,
            'assignee': assignee.email if assignee else None
        }
    
    def _create_decision_from_suggestion(self, suggestion: CopilotSuggestion, user_id: str) -> Dict[str, Any]:
        """Create decision from suggestion (stored in minutes)"""
        from transcription.models import Minutes
        
        payload = suggestion.payload_json
        
        # Find or create minutes
        minutes, _ = Minutes.objects.get_or_create(
            meeting=suggestion.meeting,
            defaults={'transcript': suggestion.meeting.transcripts.first()}
        )
        
        # Add decision to minutes content
        if 'decisions' not in minutes.content_json:
            minutes.content_json['decisions'] = []
        
        decision_data = {
            'id': str(suggestion.id),
            'text': payload['text'],
            'evidence': payload['evidence'],
            'accepted_by': user_id,
            'accepted_at': timezone.now().isoformat()
        }
        
        minutes.content_json['decisions'].append(decision_data)
        minutes.save()
        
        return {
            'type': 'decision',
            'id': str(suggestion.id),
            'text': payload['text']
        }
    
    def _create_risk_from_suggestion(self, suggestion: CopilotSuggestion, user_id: str) -> Dict[str, Any]:
        """Create risk from suggestion (stored in minutes)"""
        from transcription.models import Minutes
        
        payload = suggestion.payload_json
        
        # Find or create minutes
        minutes, _ = Minutes.objects.get_or_create(
            meeting=suggestion.meeting,
            defaults={'transcript': suggestion.meeting.transcripts.first()}
        )
        
        # Add risk to minutes content
        if 'risks' not in minutes.content_json:
            minutes.content_json['risks'] = []
        
        risk_data = {
            'id': str(suggestion.id),
            'text': payload['text'],
            'severity': payload['severity'],
            'evidence': payload['evidence'],
            'identified_by': user_id,
            'identified_at': timezone.now().isoformat()
        }
        
        minutes.content_json['risks'].append(risk_data)
        minutes.save()
        
        return {
            'type': 'risk',
            'id': str(suggestion.id),
            'text': payload['text'],
            'severity': payload['severity']
        }
    
    def _create_question_from_suggestion(self, suggestion: CopilotSuggestion, user_id: str) -> Dict[str, Any]:
        """Create open question from suggestion (stored in minutes)"""
        from transcription.models import Minutes
        
        payload = suggestion.payload_json
        
        # Find or create minutes
        minutes, _ = Minutes.objects.get_or_create(
            meeting=suggestion.meeting,
            defaults={'transcript': suggestion.meeting.transcripts.first()}
        )
        
        # Add question to minutes content
        if 'open_questions' not in minutes.content_json:
            minutes.content_json['open_questions'] = []
        
        question_data = {
            'id': str(suggestion.id),
            'text': payload['text'],
            'owner': payload.get('owner', {}),
            'evidence': payload['evidence'],
            'captured_by': user_id,
            'captured_at': timezone.now().isoformat()
        }
        
        minutes.content_json['open_questions'].append(question_data)
        minutes.save()
        
        return {
            'type': 'open_question',
            'id': str(suggestion.id),
            'text': payload['text']
        }
    
    def _broadcast_suggestion_status_update(self, suggestion: CopilotSuggestion) -> None:
        """Broadcast suggestion status update to clients"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                f"meeting_{suggestion.meeting.id}",
                {
                    'type': 'copilot_suggestion_status_updated',
                    'data': {
                        'suggestion_id': str(suggestion.id),
                        'status': suggestion.status,
                        'meeting_id': str(suggestion.meeting.id)
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error broadcasting suggestion status update: {str(e)}")


# Global orchestrator instance
copilot_orchestrator = CopilotOrchestrator()