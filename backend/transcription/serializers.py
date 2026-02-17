from rest_framework import serializers
from .models import Transcript, TranscriptSegment, Minutes, MinutesVersion, ActionItem


class TranscriptSegmentSerializer(serializers.ModelSerializer):
    speaker_label = serializers.CharField(source='speaker.label', read_only=True)
    speaker_display_name = serializers.CharField(source='speaker.display_name', read_only=True)

    class Meta:
        model = TranscriptSegment
        fields = [
            'id', 'start_ms', 'end_ms', 'speaker', 'speaker_label',
            'speaker_display_name', 'speaker_label_raw', 'text',
            'confidence', 'is_final', 'created_at'
        ]
        read_only_fields = [
            'id', 'start_ms', 'end_ms', 'speaker', 'speaker_label_raw',
            'text', 'confidence', 'is_final', 'created_at'
        ]


class TranscriptSerializer(serializers.ModelSerializer):
    segments = TranscriptSegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Transcript
        fields = ['id', 'meeting', 'recording', 'live_session', 'provider', 'language_detected', 'segments', 'created_at']
        read_only_fields = ['id', 'meeting', 'recording', 'live_session', 'provider', 'language_detected', 'created_at']


class ActionItemSerializer(serializers.ModelSerializer):
    assignee_email = serializers.EmailField(source='assignee.email', read_only=True)

    class Meta:
        model = ActionItem
        fields = [
            'id', 'meeting', 'minutes', 'title', 'description', 'assignee',
            'assignee_email', 'due_date', 'priority', 'status',
            'source_segment_ids', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'meeting', 'minutes', 'created_at', 'updated_at']


class MinutesSerializer(serializers.ModelSerializer):
    action_items = ActionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Minutes
        fields = [
            'id', 'meeting', 'transcript', 'content_json', 'content_md',
            'output_language', 'generated_by_model', 'model_version',
            'action_items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'meeting', 'transcript', 'generated_by_model',
            'model_version', 'created_at', 'updated_at'
        ]


class MinutesVersionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = MinutesVersion
        fields = ['id', 'content_json', 'created_by', 'created_by_email', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']
