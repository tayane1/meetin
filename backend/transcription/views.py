from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from meetings.models import Meeting
from .models import Transcript, Minutes, MinutesVersion, ActionItem
from .serializers import TranscriptSerializer, MinutesSerializer, ActionItemSerializer, MinutesVersionSerializer
from .tasks import generate_minutes


class TranscriptDetailView(generics.RetrieveAPIView):
    serializer_class = TranscriptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        transcript = meeting.transcripts.order_by('-created_at').first()
        if not transcript:
            return None
        return transcript
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance is None:
            return Response({'segments': [], 'message': 'No transcript available'})
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_minutes_view(request, meeting_id):
    meeting = get_object_or_404(
        Meeting.objects.filter(organization__members__user=request.user),
        id=meeting_id
    )
    
    # Check if transcript exists
    if not meeting.transcripts.exists():
        return Response({'error': 'No transcript available for this meeting'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Trigger minutes generation
    task = generate_minutes.delay(meeting_id)
    
    return Response({
        'message': 'Minutes generation started',
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)


class MinutesDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MinutesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        minutes, created = Minutes.objects.get_or_create(
            meeting=meeting,
            defaults={'transcript': meeting.transcripts.first()}
        )
        return minutes


class MinutesVersionListView(generics.ListAPIView):
    serializer_class = MinutesVersionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        try:
            minutes = meeting.minutes
            return minutes.versions.all()
        except Minutes.DoesNotExist:
            return MinutesVersion.objects.none()


class ActionItemListView(generics.ListCreateAPIView):
    serializer_class = ActionItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        return meeting.action_items.all().select_related('assignee')

    def perform_create(self, serializer):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        minutes = meeting.minutes
        serializer.save(meeting=meeting, minutes=minutes)


class ActionItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ActionItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        meeting_id = self.kwargs['meeting_id']
        meeting = get_object_or_404(
            Meeting.objects.filter(organization__members__user=self.request.user),
            id=meeting_id
        )
        
        return meeting.action_items.all()
