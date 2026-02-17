import uuid
from django.db import models
from django.conf import settings
from meetings.models import Meeting, Recording, LiveSession, Speaker


class Transcript(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='transcripts')
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, null=True, blank=True, related_name='transcripts')
    live_session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, null=True, blank=True, related_name='transcripts')
    provider = models.CharField(max_length=50, default='deepgram')
    language_detected = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transcripts'

    def __str__(self):
        return f"Transcript for {self.meeting.title} ({self.provider})"


class TranscriptSegment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(Transcript, on_delete=models.CASCADE, related_name='segments')
    start_ms = models.IntegerField()
    end_ms = models.IntegerField()
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE, null=True, blank=True, related_name='segments')
    speaker_label_raw = models.CharField(max_length=100, null=True, blank=True)  # provider label
    text = models.TextField()
    confidence = models.FloatField(null=True, blank=True)
    is_final = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transcript_segments'
        indexes = [
            models.Index(fields=['transcript', 'start_ms']),
            models.Index(fields=['start_ms', 'end_ms']),
        ]

    def __str__(self):
        return f"Segment {self.start_ms}-{self.end_ms}ms: {self.text[:50]}..."


class Minutes(models.Model):
    class OutputLanguage(models.TextChoices):
        ENGLISH = 'en', 'English'
        FRENCH = 'fr', 'French'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='minutes')
    transcript = models.ForeignKey(Transcript, on_delete=models.CASCADE, related_name='minutes')
    content_json = models.JSONField(default=dict)
    content_md = models.TextField(blank=True)
    output_language = models.CharField(max_length=10, choices=OutputLanguage.choices, default=OutputLanguage.ENGLISH)
    generated_by_model = models.CharField(max_length=100, null=True, blank=True)
    model_version = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'minutes'

    def __str__(self):
        return f"Minutes for {self.meeting.title}"


class MinutesVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    minutes = models.ForeignKey(Minutes, on_delete=models.CASCADE, related_name='versions')
    content_json = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_minutes_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'minutes_versions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Version of minutes for {self.minutes.meeting.title}"


class ActionItem(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'
        BLOCKED = 'blocked', 'Blocked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='action_items')
    minutes = models.ForeignKey(Minutes, on_delete=models.CASCADE, related_name='action_items')
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_action_items')
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    source_segment_ids = models.JSONField(default=list, blank=True)  # Array of segment UUIDs
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'action_items'
        indexes = [
            models.Index(fields=['meeting', 'status']),
        ]

    def __str__(self):
        return f"Action item: {self.title}"
