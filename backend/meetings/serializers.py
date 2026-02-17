from rest_framework import serializers
from .models import Meeting, LiveSession, Recording, Speaker, LanguagePreference


class SpeakerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Speaker
        fields = ['id', 'label', 'display_name', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recording
        fields = ['id', 'storage_key', 'mime_type', 'duration_ms', 'size_bytes', 'status', 'created_at', 'uploaded_at']
        read_only_fields = ['id', 'status', 'created_at', 'uploaded_at']


class LiveSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveSession
        fields = ['id', 'status', 'provider', 'provider_session_id', 'config_json', 'error_message', 'started_at', 'ended_at']
        read_only_fields = ['id', 'provider_session_id', 'started_at', 'ended_at']


class MeetingSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    live_sessions = LiveSessionSerializer(many=True, read_only=True)
    recordings = RecordingSerializer(many=True, read_only=True)
    speakers = SpeakerSerializer(many=True, read_only=True)
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'organization', 'organization_name', 'created_by', 'title', 'description',
            'language_preference', 'scheduled_at', 'created_at', 'updated_at',
            'live_sessions', 'recordings', 'speakers'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_organization(self, value):
        user = self.context['request'].user
        if not value.members.filter(user=user).exists():
            raise serializers.ValidationError("You don't have access to this organization")
        return value


class MeetingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'organization', 'title', 'description', 'language_preference', 'scheduled_at']
        read_only_fields = ['id']

    def validate_organization(self, value):
        user = self.context['request'].user
        if not value.members.filter(user=user).exists():
            raise serializers.ValidationError("You don't have access to this organization")
        return value