import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from transcription.models import TranscriptSegment
from meetings.models import LiveSession
from .services.orchestrator import copilot_orchestrator

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TranscriptSegment)
def handle_transcript_segment_saved(sender, instance, created, **kwargs):
    """
    Signal handler for when a transcript segment is saved.
    Triggers Copilot incremental analysis for final segments.
    """
    if not created or not instance.is_final:
        return
    
    try:
        # Check if this is part of a live session
        transcript = instance.transcript
        if transcript.live_session and transcript.live_session.status == 'active':
            # Trigger incremental analysis
            copilot_orchestrator.handle_final_transcript_segment(
                str(transcript.meeting.id),
                str(instance.id)
            )
    except Exception as e:
        logger.error(f"Error in transcript segment signal handler: {str(e)}")


@receiver(post_save, sender=LiveSession)
def handle_live_session_saved(sender, instance, created, **kwargs):
    """
    Signal handler for when a live session is saved.
    Triggers Copilot analysis when session ends.
    """
    if created or instance.status != 'ended':
        return
    
    try:
        # Run post-meeting analysis when live session ends
        copilot_orchestrator.run_post_meeting_analysis(str(instance.meeting.id))
    except Exception as e:
        logger.error(f"Error in live session signal handler: {str(e)}")