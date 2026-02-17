import logging

from celery import shared_task
from django.utils import timezone
from .services.orchestrator import copilot_orchestrator
from .models import CopilotRun

logger = logging.getLogger('meetin')


@shared_task(bind=True, max_retries=3)
def run_copilot_analysis(self, meeting_id: str, mode: str = 'post_meeting'):
    """
    Celery task to run Copilot analysis.
    
    Args:
        meeting_id: Meeting ID
        mode: Analysis mode ('post_meeting' or 'realtime_incremental')
    """
    try:
        if mode == 'post_meeting':
            run = copilot_orchestrator.run_post_meeting_analysis(meeting_id)
            return f"Post-meeting analysis completed for {meeting_id}"
        else:
            # For incremental mode, we'd need to trigger the orchestrator differently
            # This would typically be called from the transcript segment handler
            return f"Incremental analysis triggered for {meeting_id}"
            
    except Exception as e:
        logger.exception("Copilot analysis failed for meeting %s", meeting_id)
        # Log error and retry if appropriate
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(countdown=countdown, exc=e)

        # Create failed run record for tracking
        try:
            from meetings.models import Meeting
            meeting = Meeting.objects.get(id=meeting_id)
            CopilotRun.objects.create(
                meeting=meeting,
                mode=mode,
                provider='unknown',
                model='unknown',
                status=CopilotRun.RunStatus.FAILED,
                error_message=str(e),
                finished_at=timezone.now()
            )
        except Exception:
            logger.exception("Failed to create error run record for meeting %s", meeting_id)

        return f"Failed to run Copilot analysis for {meeting_id}"


@shared_task
def cleanup_old_copilot_data():
    """
    Clean up old Copilot data based on retention policies.
    """
    from datetime import timedelta
    from django.conf import settings
    
    # Get retention period (default 90 days)
    retention_days = getattr(settings, 'COPILOT_RETENTION_DAYS', 90)
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Clean up old runs
    old_runs = CopilotRun.objects.filter(
        started_at__lt=cutoff_date,
        status__in=[CopilotRun.RunStatus.SUCCESS, CopilotRun.RunStatus.FAILED]
    )
    runs_deleted = old_runs.count()
    old_runs.delete()
    
    # Clean up old rejected suggestions
    from .models import CopilotSuggestion
    old_suggestions = CopilotSuggestion.objects.filter(
        created_at__lt=cutoff_date,
        status=CopilotSuggestion.SuggestionStatus.REJECTED
    )
    suggestions_deleted = old_suggestions.count()
    old_suggestions.delete()
    
    return f"Cleaned up {runs_deleted} old runs and {suggestions_deleted} old suggestions"


@shared_task
def send_copilot_notifications():
    """
    Send scheduled Copilot notifications (action item reminders, etc.).
    """
    from datetime import datetime
    from .models import CopilotNotification
    
    # Get due notifications
    due_notifications = CopilotNotification.objects.filter(
        scheduled_at__lte=timezone.now(),
        status=CopilotNotification.NotificationStatus.SCHEDULED
    )
    
    sent_count = 0
    for notification in due_notifications:
        try:
            # Here you would implement the actual notification sending
            # (email, push notification, etc.)
            
            # For now, just mark as sent
            notification.status = CopilotNotification.NotificationStatus.SENT
            notification.sent_at = timezone.now()
            notification.save()
            
            sent_count += 1
            
        except Exception as e:
            # Mark as failed and increment retry count
            notification.status = CopilotNotification.NotificationStatus.FAILED
            notification.retry_count += 1
            notification.last_error = str(e)
            notification.save()
    
    return f"Sent {sent_count} Copilot notifications"