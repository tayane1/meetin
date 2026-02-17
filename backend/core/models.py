import uuid
from django.db import models
from django.conf import settings
from meetings.models import Meeting


class ShareLink(models.Model):
    class Permission(models.TextChoices):
        VIEW = 'view', 'View'
        COMMENT = 'comment', 'Comment'
        EDIT = 'edit', 'Edit'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='share_links')
    token = models.CharField(max_length=255, unique=True)
    permission = models.CharField(max_length=20, choices=Permission.choices, default=Permission.VIEW)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_share_links')

    class Meta:
        db_table = 'share_links'

    def __str__(self):
        return f"Share link for {self.meeting.title} ({self.permission})"

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at and self.expires_at < timezone.now()


class AuditLog(models.Model):
    class EntityType(models.TextChoices):
        MEETING = 'meeting', 'Meeting'
        TRANSCRIPT = 'transcript', 'Transcript'
        MINUTES = 'minutes', 'Minutes'
        USER = 'user', 'User'
        ORGANIZATION = 'organization', 'Organization'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audit_actions')
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    entity_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
        ]

    def __str__(self):
        return f"{self.actor.email} {self.action} {self.entity_type} {self.entity_id}"
