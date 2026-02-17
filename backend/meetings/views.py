import logging
import os
import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Meeting, LiveSession, Recording, Speaker
from .serializers import (
    MeetingSerializer, MeetingCreateSerializer,
    LiveSessionSerializer, RecordingSerializer, SpeakerSerializer,
)
from transcription.services import TranscriptionService

logger = logging.getLogger('meetin')


class MeetingListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meeting.objects.filter(
            organization__members__user=self.request.user
        ).distinct().select_related('organization', 'created_by')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MeetingCreateSerializer
        return MeetingSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MeetingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meeting.objects.filter(
            organization__members__user=self.request.user
        ).distinct().select_related('organization', 'created_by')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def start_live_session(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    # Check if there's already an active session
    active_session = meeting.live_sessions.filter(status=LiveSession.Status.ACTIVE).first()
    if active_session:
        return Response({'error': 'Live session already active'}, status=status.HTTP_400_BAD_REQUEST)

    # Create new live session
    session = LiveSession.objects.create(
        meeting=meeting,
        config_json=request.data.get('config', {})
    )

    # Start transcription service
    transcription_service = TranscriptionService()
    try:
        session.provider_session_id = transcription_service.start_live_session(session)
        session.save()
        return Response(LiveSessionSerializer(session).data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception("Failed to start live session for meeting %s", meeting_id)
        session.status = LiveSession.Status.FAILED
        session.error_message = str(e)
        session.save()
        return Response(
            {'error': 'Failed to start live session. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def stop_live_session(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    session = meeting.live_sessions.filter(status=LiveSession.Status.ACTIVE).first()
    if not session:
        return Response({'error': 'No active live session'}, status=status.HTTP_404_NOT_FOUND)

    transcription_service = TranscriptionService()
    try:
        transcription_service.stop_live_session(session)
        session.status = LiveSession.Status.ENDED
        session.ended_at = timezone.now()
        session.save()
        return Response(LiveSessionSerializer(session).data)
    except Exception as e:
        logger.exception("Failed to stop live session for meeting %s", meeting_id)
        return Response(
            {'error': 'Failed to stop live session. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def live_session_status(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    session = meeting.live_sessions.filter(status=LiveSession.Status.ACTIVE).first()
    if not session:
        return Response({'status': 'no_active_session'}, status=status.HTTP_404_NOT_FOUND)

    return Response(LiveSessionSerializer(session).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initiate_recording(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    recording = Recording.objects.create(
        meeting=meeting,
        storage_key=f"recordings/{meeting.id}/{uuid.uuid4()}.webm"
    )

    # Generate signed upload URL (implementation depends on storage backend)
    from core.storage import generate_upload_url
    upload_url = generate_upload_url(recording.storage_key)

    return Response({
        'recording_id': recording.id,
        'upload_url': upload_url,
        'storage_key': recording.storage_key
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def complete_recording(request, recording_id):
    recording = get_object_or_404(
        Recording.objects.filter(meeting__organization__members__user=request.user),
        id=recording_id
    )

    recording.status = Recording.Status.UPLOADED
    recording.uploaded_at = timezone.now()

    # Validate integer fields
    size_bytes = request.data.get('size_bytes')
    duration_ms = request.data.get('duration_ms')

    if size_bytes is not None:
        try:
            size_bytes = int(size_bytes)
            if size_bytes < 0 or size_bytes > settings.MAX_AUDIO_FILE_SIZE:
                return Response({'error': 'Invalid size_bytes value'}, status=status.HTTP_400_BAD_REQUEST)
            recording.size_bytes = size_bytes
        except (ValueError, TypeError):
            return Response({'error': 'size_bytes must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)

    if duration_ms is not None:
        try:
            duration_ms = int(duration_ms)
            if duration_ms < 0 or duration_ms > 86400000:  # max 24 hours
                return Response({'error': 'Invalid duration_ms value'}, status=status.HTTP_400_BAD_REQUEST)
            recording.duration_ms = duration_ms
        except (ValueError, TypeError):
            return Response({'error': 'duration_ms must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)

    recording.save()

    # Trigger transcription
    from transcription.tasks import transcribe_recording
    transcribe_recording.delay(recording.id)

    return Response(RecordingSerializer(recording).data)


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_speaker(request, meeting_id, speaker_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    speaker = get_object_or_404(
        Speaker.objects.filter(meeting=meeting),
        id=speaker_id
    )

    display_name = request.data.get('display_name')
    if display_name:
        if len(display_name) > 255:
            return Response({'error': 'Display name too long'}, status=status.HTTP_400_BAD_REQUEST)
        speaker.display_name = display_name
        speaker.save()

    return Response(SpeakerSerializer(speaker).data)


def _validate_audio_file(audio_file):
    """Validate uploaded audio file for security."""
    # Check file size
    max_size = getattr(settings, 'MAX_AUDIO_FILE_SIZE', 500 * 1024 * 1024)
    if audio_file.size > max_size:
        return f'File too large. Maximum size is {max_size // (1024 * 1024)}MB.'

    # Check file extension
    file_ext = os.path.splitext(audio_file.name)[1].lower()
    allowed_extensions = getattr(settings, 'ALLOWED_AUDIO_EXTENSIONS', {'.webm', '.wav', '.mp3', '.m4a'})
    if file_ext not in allowed_extensions:
        return f'Invalid file type. Allowed: {", ".join(sorted(allowed_extensions))}'

    # Check MIME type
    allowed_mimes = getattr(settings, 'ALLOWED_AUDIO_MIME_TYPES', {'audio/webm'})
    if audio_file.content_type not in allowed_mimes:
        return f'Invalid MIME type: {audio_file.content_type}'

    return None


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_recording(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    if 'audio' not in request.FILES:
        return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)

    audio_file = request.FILES['audio']

    # Validate file
    validation_error = _validate_audio_file(audio_file)
    if validation_error:
        return Response({'error': validation_error}, status=status.HTTP_400_BAD_REQUEST)

    # Use safe extension from whitelist
    file_ext = os.path.splitext(audio_file.name)[1].lower()
    storage_key = f"recordings/{meeting.id}/{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.MEDIA_ROOT, storage_key)

    # Path traversal protection
    resolved_path = os.path.realpath(file_path)
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    if not resolved_path.startswith(media_root + os.sep):
        return Response({'error': 'Invalid file path'}, status=status.HTTP_400_BAD_REQUEST)

    recordings_dir = os.path.dirname(file_path)
    os.makedirs(recordings_dir, exist_ok=True)

    with open(file_path, 'wb+') as destination:
        for chunk in audio_file.chunks():
            destination.write(chunk)

    recording = Recording.objects.create(
        meeting=meeting,
        storage_key=storage_key,
        status=Recording.Status.UPLOADED,
        uploaded_at=timezone.now(),
        size_bytes=audio_file.size
    )

    return Response(RecordingSerializer(recording).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def transcribe_recording_view(request, meeting_id, recording_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    recording = get_object_or_404(
        Recording.objects.filter(meeting=meeting),
        id=recording_id
    )

    try:
        from transcription.services import BatchTranscriptionService
        service = BatchTranscriptionService()
        service.transcribe_recording(recording)

        from transcription.models import Transcript
        transcript = Transcript.objects.filter(recording=recording).last()

        if transcript:
            segments = transcript.segments.all().order_by('start_ms')
            return Response({
                'status': 'completed',
                'transcript_id': str(transcript.id),
                'segments': [
                    {
                        'id': str(s.id),
                        'start_ms': s.start_ms,
                        'end_ms': s.end_ms,
                        'speaker_label': s.speaker_label_raw,
                        'speaker_display_name': s.speaker.display_name if s.speaker else None,
                        'text': s.text,
                        'confidence': s.confidence,
                        'is_final': s.is_final,
                    }
                    for s in segments
                ]
            })

        return Response({'status': 'completed', 'message': 'No transcript generated'})

    except Exception as e:
        logger.exception("Failed to transcribe recording %s", recording_id)
        return Response(
            {'error': 'Transcription failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
