import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from meetings.models import Meeting, LiveSession
from transcription.services import TranscriptionService

logger = logging.getLogger('meetin')


class LiveTranscriptionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.meeting_id = self.scope['url_route']['kwargs']['meeting_id']
        self.meeting_group_name = f"meeting_{self.meeting_id}"
        
        # Verify user has access to this meeting
        if not await self.has_meeting_access():
            await self.close()
            return
        
        # Join meeting group
        await self.channel_layer.group_add(
            self.meeting_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave meeting group
        await self.channel_layer.group_discard(
            self.meeting_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming WebSocket messages"""
        try:
            if text_data:
                message = json.loads(text_data)
                message_type = message.get('type')
                
                if message_type == 'audio_chunk':
                    # Forward audio to transcription service
                    await self.handle_audio_chunk(message.get('data'))
                elif message_type == 'control':
                    # Handle control messages (start, stop, pause)
                    await self.handle_control_message(message)
                elif message_type == 'speaker_mapping':
                    # Handle speaker name mapping
                    await self.handle_speaker_mapping(message)
                    
            elif bytes_data:
                # Handle binary audio data
                await self.handle_binary_audio(bytes_data)
                
        except json.JSONDecodeError:
            await self.send_json({
                'type': 'error',
                'message': 'Invalid message format'
            })
        except Exception as e:
            logger.exception("Error processing WebSocket message")
            await self.send_json({
                'type': 'error',
                'message': 'An error occurred processing your message'
            })
    
    async def handle_audio_chunk(self, audio_data):
        """Forward audio chunk to transcription service"""
        # Get active live session
        session = await self.get_active_session()
        if not session:
            await self.send_json({
                'type': 'error',
                'message': 'No active transcription session'
            })
            return
        
        # Send to transcription service
        transcription_service = TranscriptionService()
        await transcription_service.process_audio_chunk(session, audio_data)
    
    async def handle_binary_audio(self, audio_data):
        """Handle binary audio data"""
        session = await self.get_active_session()
        if not session:
            return
        
        transcription_service = TranscriptionService()
        await transcription_service.process_binary_audio(session, audio_data)
    
    async def handle_control_message(self, message):
        """Handle control messages"""
        control_type = message.get('control')
        
        if control_type == 'start':
            # Start transcription (handled via REST API)
            await self.send_json({
                'type': 'control_response',
                'control': control_type,
                'status': 'use_api_to_start'
            })
        elif control_type == 'stop':
            # Stop transcription
            await self.stop_transcription()
    
    async def handle_speaker_mapping(self, message):
        """Handle speaker name mapping"""
        speaker_label = message.get('speaker_label')
        display_name = message.get('display_name')

        # Validate inputs
        if not speaker_label or not isinstance(speaker_label, str) or len(speaker_label) > 100:
            await self.send_json({'type': 'error', 'message': 'Invalid speaker_label'})
            return
        if not display_name or not isinstance(display_name, str) or len(display_name) > 255:
            await self.send_json({'type': 'error', 'message': 'Invalid display_name'})
            return

        # Update speaker in database
        from meetings.models import Speaker
        await database_sync_to_async(
            Speaker.objects.filter(
                meeting_id=self.meeting_id,
                label=speaker_label
            ).update
        )(display_name=display_name)
        
        # Broadcast to all clients
        await self.channel_layer.group_send(
            self.meeting_group_name,
            {
                'type': 'speaker_updated',
                'speaker_label': speaker_label,
                'display_name': display_name
            }
        )
    
    async def stop_transcription(self):
        """Stop transcription session"""
        session = await self.get_active_session()
        if session:
            transcription_service = TranscriptionService()
            await transcription_service.stop_live_session(session)
    
    # Channel layer message handlers
    async def transcript_segment(self, event):
        """Send transcript segment to client"""
        await self.send_json({
            'type': 'transcript_segment',
            'data': event['data']
        })
    
    async def speaker_updated(self, event):
        """Send speaker update to client"""
        await self.send_json({
            'type': 'speaker_updated',
            'speaker_label': event['speaker_label'],
            'display_name': event['display_name']
        })
    
    async def session_status(self, event):
        """Send session status update to client"""
        await self.send_json({
            'type': 'session_status',
            'status': event['status'],
            'message': event.get('message')
        })
    
    # Helper methods
    @database_sync_to_async
    def has_meeting_access(self):
        """Check if user has access to this meeting"""
        user = self.scope.get('user', AnonymousUser())
        if user.is_anonymous:
            return False
        
        try:
            meeting = Meeting.objects.get(
                id=self.meeting_id,
                organization__members__user=user
            )
            self.meeting = meeting
            return True
        except Meeting.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_active_session(self):
        """Get active live session for this meeting"""
        try:
            return LiveSession.objects.get(
                meeting_id=self.meeting_id,
                status=LiveSession.Status.ACTIVE
            )
        except LiveSession.DoesNotExist:
            return None
    
    def send_json(self, data):
        """Send JSON message to client"""
        return self.send(text_data=json.dumps(data))