import uuid
from django.db import models
from django.conf import settings
from accounts.models import Organization


class LanguagePreference(models.TextChoices):
    ENGLISH = 'en', 'English'
    FRENCH = 'fr', 'French'
    AUTO = 'auto', 'Auto-detect'


class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='meetings')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_meetings')
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    language_preference = models.CharField(max_length=10, choices=LanguagePreference.choices, default=LanguagePreference.AUTO)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meetings'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.organization.name})"


class LiveSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ENDED = 'ended', 'Ended'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='live_sessions')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    provider = models.CharField(max_length=50, default='deepgram')
    provider_session_id = models.CharField(max_length=255, null=True, blank=True)
    config_json = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'live_sessions'

    def __str__(self):
        return f"Live session for {self.meeting.title} ({self.status})"


class Recording(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        UPLOADED = 'uploaded', 'Uploaded'
        PROCESSING = 'processing', 'Processing'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='recordings')
    storage_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, default='audio/webm')
    duration_ms = models.IntegerField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recordings'

    def __str__(self):
        return f"Recording for {self.meeting.title} ({self.status})"


class Speaker(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='speakers')
    label = models.CharField(max_length=100)  # e.g., "Speaker 1"
    display_name = models.CharField(max_length=255, null=True, blank=True)  # e.g., "Alice"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'speakers'
        unique_together = ['meeting', 'label']

    def __str__(self):
        name = self.display_name or self.label
        return f"{name} in {self.meeting.title}"
