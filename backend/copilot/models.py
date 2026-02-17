from django.db import models
from django.conf import settings
from meetings.models import Meeting, Speaker
from accounts.models import User
import uuid


class CopilotSuggestion(models.Model):
    class SuggestionType(models.TextChoices):
        ACTION_ITEM = 'action_item', 'Action Item'
        DECISION = 'decision', 'Decision'
        RISK = 'risk', 'Risk'
        QUESTION = 'question', 'Open Question'
    
    class SuggestionStatus(models.TextChoices):
        PROPOSED = 'proposed', 'Proposed'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        EDITED = 'edited', 'Edited'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='copilot_suggestions')
    type = models.CharField(max_length=20, choices=SuggestionType.choices)
    payload_json = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=SuggestionStatus.choices, default=SuggestionStatus.PROPOSED)
    dedupe_key = models.CharField(max_length=255, db_index=True)
    source_segment_ids = models.JSONField(default=list, blank=True)  # Array of segment UUIDs
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=10, choices=[('ai', 'AI'), ('user', 'User')], default='ai')
    
    # Link to accepted entity
    accepted_action_item = models.ForeignKey(
        'transcription.ActionItem', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='source_suggestion'
    )
    
    class Meta:
        db_table = 'copilot_suggestions'
        indexes = [
            models.Index(fields=['meeting', 'type', 'status']),
            models.Index(fields=['meeting', 'dedupe_key']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} for {self.meeting.title} ({self.status})"
    
    def clean(self):
        """Ensure evidence is provided"""
        if not self.source_segment_ids:
            raise models.ValidationError("Evidence (source_segment_ids) is required for all suggestions")


class CopilotRun(models.Model):
    class RunMode(models.TextChoices):
        REALTIME_INCREMENTAL = 'realtime_incremental', 'Real-time Incremental'
        POST_MEETING = 'post_meeting', 'Post-meeting'
    
    class RunStatus(models.TextChoices):
        STARTED = 'started', 'Started'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        TIMEOUT = 'timeout', 'Timeout'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='copilot_runs')
    mode = models.CharField(max_length=30, choices=RunMode.choices)
    provider = models.CharField(max_length=50, default='openai')
    model = models.CharField(max_length=100)
    input_token_count = models.IntegerField(null=True, blank=True)
    output_token_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=RunStatus.choices, default=RunStatus.STARTED)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Run metadata
    segment_count = models.IntegerField(null=True, blank=True)
    suggestion_count = models.IntegerField(null=True, blank=True)
    processing_time_ms = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'copilot_runs'
        indexes = [
            models.Index(fields=['meeting', 'started_at']),
            models.Index(fields=['status', 'started_at']),
        ]
    
    def __str__(self):
        return f"Copilot run for {self.meeting.title} ({self.mode})"


class SpeakerUserMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='speaker_user_maps')
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE, related_name='user_maps')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='speaker_maps')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_speaker_maps'
    )
    
    class Meta:
        db_table = 'speaker_user_map'
        unique_together = ['meeting', 'speaker']
        indexes = [
            models.Index(fields=['meeting', 'user']),
        ]
    
    def __str__(self):
        return f"{self.speaker.label} → {self.user.email} in {self.meeting.title}"


class CopilotFollowUp(models.Model):
    """Tracks follow-up items and next meeting preparation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='copilot_followup')
    previous_meeting = models.ForeignKey(
        Meeting, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='next_follow_up'
    )
    
    # Follow-up content
    unresolved_items_json = models.JSONField(default=list, blank=True)
    changes_since_last_meeting = models.TextField(blank=True)
    suggested_next_agenda = models.JSONField(default=list, blank=True)
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    copilot_run = models.ForeignKey(CopilotRun, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'copilot_follow_up'
    
    def __str__(self):
        return f"Follow-up for {self.meeting.title}"


class CopilotNotification(models.Model):
    """Tracks scheduled notifications for action items and follow-ups"""
    class NotificationType(models.TextChoices):
        ACTION_DUE = 'action_due', 'Action Item Due'
        ACTION_OVERDUE = 'action_overdue', 'Action Item Overdue'
        WEEKLY_DIGEST = 'weekly_digest', 'Weekly Digest'
        MEETING_REMINDER = 'meeting_reminder', 'Meeting Reminder'
    
    class NotificationStatus(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='copilot_notifications')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='copilot_notifications')
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    status = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.SCHEDULED)
    
    # Notification content
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.URLField(null=True, blank=True)
    
    # Scheduling
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Related entities
    action_item = models.ForeignKey(
        'transcription.ActionItem',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Retry tracking
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'copilot_notifications'
        indexes = [
            models.Index(fields=['user', 'scheduled_at', 'status']),
            models.Index(fields=['meeting', 'type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} for {self.user.email} ({self.status})"