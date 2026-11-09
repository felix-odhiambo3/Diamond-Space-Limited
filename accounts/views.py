from django.contrib.auth import get_user_model

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdminOrOwner, IsOwner
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserListSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)

            if token['user_id'] != request.user.id:
                return Response(
                    {'error': 'Invalid refresh token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token.blacklist()

            return Response(
                {'message': 'Successfully logged out.'},
                status=status.HTTP_200_OK
            )

        except TokenError:
            return Response(
                {'error': 'Invalid or expired refresh token.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
        })


class OwnerTestView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        return Response({
            'message': 'Access granted. You are an Owner.',
            'role': request.user.role,
        })


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrOwner]

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')

        # Admins cannot view Owner or superuser accounts.
        if (
            not self.request.user.is_superuser
            and self.request.user.role != User.Role.OWNER
        ):
            queryset = queryset.exclude(
                role=User.Role.OWNER
            ).exclude(
                is_superuser=True
            )

        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer

        return UserListSerializer


class UserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminOrOwner]
    serializer_class = UserUpdateSerializer

    def get_queryset(self):
        queryset = User.objects.all()

        # Admins cannot retrieve or modify Owner or superuser accounts.
        if (
            not self.request.user.is_superuser
            and self.request.user.role != User.Role.OWNER
        ):
            queryset = queryset.exclude(
                role=User.Role.OWNER
            ).exclude(
                is_superuser=True
            )

        return queryset


class UserDeactivateView(APIView):
    permission_classes = [IsAdminOrOwner]

    def patch(self, request, pk):
        queryset = User.objects.all()

        if (
            not request.user.is_superuser
            and request.user.role != User.Role.OWNER
        ):
            queryset = queryset.exclude(
                role=User.Role.OWNER
            ).exclude(
                is_superuser=True
            )

        try:
            user = queryset.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.pk == request.user.pk:
            return Response(
                {'error': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_active = False
        user.save(update_fields=['is_active'])

        return Response(
            {'message': 'User successfully deactivated.'},
            status=status.HTTP_200_OK
        )