import logging

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from meetings.models import Meeting, Speaker
from accounts.models import User, OrganizationMember
from .models import CopilotSuggestion, CopilotRun, SpeakerUserMap
from .serializers import (
    CopilotSuggestionSerializer, CopilotRunSerializer,
    SpeakerUserMapSerializer, SpeakerUserMapCreateSerializer,
    CopilotSuggestionActionSerializer
)
from .services.orchestrator import copilot_orchestrator
from .tasks import run_copilot_analysis as run_copilot_analysis_task

logger = logging.getLogger('meetin')


class CopilotSuggestionViewSet(viewsets.ModelViewSet):
    """ViewSet for Copilot suggestions"""
    serializer_class = CopilotSuggestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs.get('meeting_id')
        if not meeting_id:
            return CopilotSuggestion.objects.none()

        # Verify user has access to meeting
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )

        queryset = CopilotSuggestion.objects.filter(meeting=meeting)

        # Filter by type if provided
        suggestion_type = self.request.query_params.get('type')
        if suggestion_type:
            queryset = queryset.filter(type=suggestion_type)

        # Filter by status if provided
        suggestion_status = self.request.query_params.get('status')
        if suggestion_status:
            queryset = queryset.filter(status=suggestion_status)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def accept(self, request, meeting_id=None, pk=None):
        """Accept a suggestion and create the corresponding entity"""
        suggestion = self.get_object()

        try:
            entity_data = copilot_orchestrator.accept_suggestion(
                str(suggestion.id),
                str(request.user.id)
            )
            return Response(entity_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Failed to accept suggestion %s", pk)
            return Response(
                {'error': 'Failed to accept suggestion.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def reject(self, request, meeting_id=None, pk=None):
        """Reject a suggestion"""
        suggestion = self.get_object()
        suggestion.status = CopilotSuggestion.SuggestionStatus.REJECTED
        suggestion.save()

        # Broadcast status update
        copilot_orchestrator._broadcast_suggestion_status_update(suggestion)

        return Response({'status': 'rejected'})

    @action(detail=True, methods=['patch'])
    def edit(self, request, meeting_id=None, pk=None):
        """Edit a suggestion"""
        suggestion = self.get_object()

        if suggestion.status != CopilotSuggestion.SuggestionStatus.PROPOSED:
            return Response(
                {'error': 'Can only edit proposed suggestions'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update payload
        suggestion.payload_json = request.data.get('payload_json', suggestion.payload_json)
        suggestion.status = CopilotSuggestion.SuggestionStatus.EDITED
        suggestion.save()

        # Broadcast update
        copilot_orchestrator._broadcast_suggestion_status_update(suggestion)

        return Response(CopilotSuggestionSerializer(suggestion).data)


class CopilotRunViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Copilot runs (read-only)"""
    serializer_class = CopilotRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs.get('meeting_id')
        if not meeting_id:
            return CopilotRun.objects.none()

        # Verify user has access to meeting
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )

        return CopilotRun.objects.filter(meeting=meeting).order_by('-started_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def run_copilot_analysis_view(request, meeting_id):
    """Trigger Copilot analysis for a meeting"""
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    mode = request.data.get('mode', 'post_meeting')
    if mode not in ['post_meeting', 'realtime_incremental']:
        return Response(
            {'error': 'Invalid mode. Must be post_meeting or realtime_incremental'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        if mode == 'post_meeting':
            # Run synchronously for post-meeting
            run = copilot_orchestrator.run_post_meeting_analysis(str(meeting.id))
            return Response(CopilotRunSerializer(run).data)
        else:
            # Run asynchronously for incremental
            task = run_copilot_analysis_task.delay(str(meeting.id), mode)
            return Response({
                'message': 'Copilot analysis started',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.exception("Failed to run copilot analysis for meeting %s", meeting_id)
        return Response(
            {'error': 'Copilot analysis failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class SpeakerUserMapViewSet(viewsets.ModelViewSet):
    """ViewSet for speaker-to-user mappings"""
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return SpeakerUserMapCreateSerializer
        return SpeakerUserMapSerializer

    def get_queryset(self):
        meeting_id = self.kwargs.get('meeting_id')
        if not meeting_id:
            return SpeakerUserMap.objects.none()

        # Verify user has access to meeting
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )

        return SpeakerUserMap.objects.filter(meeting=meeting).select_related(
            'speaker', 'user'
        )

    def perform_create(self, serializer):
        meeting_id = self.kwargs.get('meeting_id')
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )

        serializer.save(
            meeting=meeting,
            created_by=self.request.user
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def copilot_status(request, meeting_id):
    """Get Copilot status for a meeting"""
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    # Get suggestion counts by type and status
    suggestions = CopilotSuggestion.objects.filter(meeting=meeting)

    status_counts = {}
    for status_choice in CopilotSuggestion.SuggestionStatus.choices:
        status_field = status_choice[0]
        status_counts[status_field] = suggestions.filter(status=status_field).count()

    type_counts = {}
    for type_choice in CopilotSuggestion.SuggestionType.choices:
        type_field = type_choice[0]
        type_counts[type_field] = suggestions.filter(type=type_field).count()

    # Get latest run info
    latest_run = CopilotRun.objects.filter(meeting=meeting).order_by('-started_at').first()

    # Get speaker mappings
    speaker_mappings = SpeakerUserMap.objects.filter(meeting=meeting).count()

    return Response({
        'meeting_id': str(meeting.id),
        'suggestion_counts': {
            'by_status': status_counts,
            'by_type': type_counts,
            'total': suggestions.count()
        },
        'latest_run': CopilotRunSerializer(latest_run).data if latest_run else None,
        'speaker_mappings_count': speaker_mappings,
        'is_live': meeting.live_sessions.filter(status='active').exists()
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def map_speaker_to_user(request, meeting_id, speaker_id):
    """Map a speaker to a user — restricted to same-organization users"""
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    speaker = get_object_or_404(Speaker, id=speaker_id, meeting=meeting)
    user_id = request.data.get('user_id')

    if not user_id:
        return Response(
            {'error': 'user_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Only allow mapping to users within the same organization
    try:
        user = User.objects.get(
            id=user_id,
            organization_memberships__organization=meeting.organization
        )
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found in this organization'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Create or update mapping
    mapping, created = SpeakerUserMap.objects.update_or_create(
        meeting=meeting,
        speaker=speaker,
        defaults={'user': user, 'created_by': request.user}
    )

    return Response({
        'mapping_id': str(mapping.id),
        'speaker_label': speaker.label,
        'user_email': user.email,
        'created': created
    })


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def unmap_speaker(request, meeting_id, speaker_id):
    """Remove speaker-to-user mapping"""
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )

    speaker = get_object_or_404(Speaker, id=speaker_id, meeting=meeting)

    try:
        mapping = SpeakerUserMap.objects.get(meeting=meeting, speaker=speaker)
        mapping.delete()
        return Response({'status': 'deleted'})
    except SpeakerUserMap.DoesNotExist:
        return Response(
            {'error': 'Mapping not found'},
            status=status.HTTP_404_NOT_FOUND
        )
