import logging

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
from .models import User, Organization, OrganizationMember
from .serializers import UserSerializer, LoginSerializer, OrganizationSerializer, OrganizationMemberSerializer

logger = logging.getLogger('meetin')


class AuthRateThrottle(AnonRateThrottle):
    rate = '10/minute'


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create default organization for new user
        organization = Organization.objects.create(
            name=f"{user.email}'s Organization",
            owner=user
        )
        OrganizationMember.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMember.Role.ADMIN
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']

    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.filter(
            members__user=self.request.user
        ).distinct()

    def perform_create(self, serializer):
        organization = serializer.save(owner=self.request.user)
        OrganizationMember.objects.create(
            organization=organization,
            user=self.request.user,
            role=OrganizationMember.Role.ADMIN
        )


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.filter(
            members__user=self.request.user,
            members__role=OrganizationMember.Role.ADMIN,
        ).distinct()


class OrganizationMemberListView(generics.ListCreateAPIView):
    serializer_class = OrganizationMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        org_id = self.kwargs['org_id']
        return OrganizationMember.objects.filter(
            organization_id=org_id,
            organization__members__user=self.request.user
        )

    def perform_create(self, serializer):
        org_id = self.kwargs['org_id']
        # Only admins can add members
        membership = OrganizationMember.objects.filter(
            organization_id=org_id,
            user=self.request.user,
            role=OrganizationMember.Role.ADMIN
        ).first()
        if not membership:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only organization admins can add members.")
        serializer.save(organization=membership.organization)
