import logging

from celery import shared_task
from django.utils import timezone
from .services import BatchTranscriptionService
from .models import Transcript, Minutes
from meetings.models import Recording
from core.ai_service import AIService

logger = logging.getLogger('meetin')


@shared_task(bind=True, max_retries=3)
def transcribe_recording(self, recording_id):
    """Transcribe a recording using batch transcription"""
    try:
        recording = Recording.objects.get(id=recording_id)
        recording.status = Recording.Status.PROCESSING
        recording.save()

        service = BatchTranscriptionService()
        service.transcribe_recording(recording)

        return f"Successfully transcribed recording {recording_id}"

    except Recording.DoesNotExist:
        logger.error("Recording %s not found", recording_id)
        return f"Recording {recording_id} not found"
    except Exception as e:
        logger.exception("Failed to transcribe recording %s", recording_id)
        # Update recording status to failed
        try:
            recording = Recording.objects.get(id=recording_id)
            recording.status = Recording.Status.FAILED
            recording.save()
        except Recording.DoesNotExist:
            logger.error("Recording %s disappeared during error handling", recording_id)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)

        return f"Failed to transcribe recording {recording_id}"


@shared_task(bind=True, max_retries=3)
def generate_minutes(self, meeting_id):
    """Generate meeting minutes from transcript"""
    try:
        from meetings.models import Meeting
        meeting = Meeting.objects.get(id=meeting_id)

        # Get the latest transcript
        transcript = meeting.transcripts.latest('created_at')

        # Generate minutes using AI service
        ai_service = AIService()
        minutes_content = ai_service.generate_minutes(
            transcript=transcript,
            language=meeting.language_preference
        )

        # Create or update minutes
        minutes, created = Minutes.objects.update_or_create(
            meeting=meeting,
            defaults={
                'transcript': transcript,
                'content_json': minutes_content,
                'content_md': ai_service.convert_to_markdown(minutes_content),
                'output_language': meeting.language_preference,
                'generated_by_model': ai_service.model_name,
                'model_version': ai_service.model_version
            }
        )

        # Extract action items
        ai_service.extract_action_items(minutes_content, minutes)

        return f"Successfully generated minutes for meeting {meeting_id}"

    except Meeting.DoesNotExist:
        logger.error("Meeting %s not found", meeting_id)
        return f"Meeting {meeting_id} not found"
    except Exception as e:
        logger.exception("Failed to generate minutes for meeting %s", meeting_id)
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)

        return f"Failed to generate minutes for meeting {meeting_id}"


@shared_task
def cleanup_old_sessions():
    """Clean up old live sessions and temporary data"""
    from meetings.models import LiveSession
    from datetime import timedelta

    # Delete sessions older than 24 hours
    cutoff_time = timezone.now() - timedelta(hours=24)
    old_sessions = LiveSession.objects.filter(
        created_at__lt=cutoff_time,
        status__in=[LiveSession.Status.ENDED, LiveSession.Status.FAILED]
    )

    count = old_sessions.count()
    old_sessions.delete()

    return f"Cleaned up {count} old sessions"


@shared_task
def process_audio_cleanup():
    """Clean up audio files based on retention policy"""
    from meetings.models import Recording
    from django.conf import settings
    from datetime import timedelta

    # Get retention period from settings (default 30 days)
    retention_days = getattr(settings, 'AUDIO_RETENTION_DAYS', 30)
    cutoff_time = timezone.now() - timedelta(days=retention_days)

    # Find old recordings
    old_recordings = Recording.objects.filter(
        created_at__lt=cutoff_time,
        status=Recording.Status.READY
    )

    deleted_count = 0
    for recording in old_recordings:
        try:
            from core.storage import delete_audio_file
            delete_audio_file(recording.storage_key)
            recording.delete()
            deleted_count += 1
        except Exception as e:
            logger.exception("Failed to delete recording %s", recording.id)

    return f"Deleted {deleted_count} old recordings"
