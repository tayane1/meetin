from rest_framework import serializers
from .models import CopilotSuggestion, CopilotRun, SpeakerUserMap, CopilotFollowUp, CopilotNotification


class CopilotSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotSuggestion
        fields = [
            'id', 'meeting', 'type', 'payload_json', 'status', 'dedupe_key',
            'source_segment_ids', 'confidence', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'id', 'meeting', 'type', 'dedupe_key', 'source_segment_ids',
            'confidence', 'created_at', 'updated_at', 'created_by'
        ]


class CopilotSuggestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotSuggestion
        fields = ['type', 'payload_json', 'dedupe_key', 'source_segment_ids', 'confidence']
    
    def validate_source_segment_ids(self, value):
        if not value:
            raise serializers.ValidationError("Evidence (source_segment_ids) is required")
        return value


class CopilotRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotRun
        fields = [
            'id', 'meeting', 'mode', 'provider', 'model', 'input_token_count',
            'output_token_count', 'status', 'error_message', 'started_at', 'finished_at',
            'segment_count', 'suggestion_count', 'processing_time_ms'
        ]
        read_only_fields = fields


class SpeakerUserMapSerializer(serializers.ModelSerializer):
    speaker_label = serializers.CharField(source='speaker.label', read_only=True)
    speaker_display_name = serializers.CharField(source='speaker.display_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = SpeakerUserMap
        fields = [
            'id', 'meeting', 'speaker', 'speaker_label', 'speaker_display_name',
            'user', 'user_email', 'user_name', 'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'meeting', 'created_at', 'created_by']


class SpeakerUserMapCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeakerUserMap
        fields = ['speaker', 'user']


class CopilotFollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotFollowUp
        fields = [
            'id', 'meeting', 'previous_meeting', 'unresolved_items_json',
            'changes_since_last_meeting', 'suggested_next_agenda',
            'generated_at', 'copilot_run'
        ]
        read_only_fields = fields


class CopilotNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotNotification
        fields = [
            'id', 'meeting', 'user', 'type', 'status', 'title', 'message',
            'action_url', 'scheduled_at', 'sent_at', 'action_item',
            'retry_count', 'last_error', 'created_at'
        ]
        read_only_fields = fields


class CopilotSuggestionActionSerializer(serializers.Serializer):
    """Serializer for suggestion actions (accept/reject/edit)"""
    action = serializers.ChoiceField(choices=['accept', 'reject', 'edit'])
    payload_json = serializers.JSONField(required=False)
    
    def validate(self, data):
        action = data.get('action')
        if action == 'edit' and 'payload_json' not in data:
            raise serializers.ValidationError("payload_json is required for edit action")
        return data