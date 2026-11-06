from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import CustomTokenObtainPairSerializer
from .permissions import IsOwner

from django.contrib.auth import get_user_model

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    UserCreateSerializer,
    UserUpdateSerializer,
    UserListSerializer,
)

from .permissions import IsAdmin

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
            'role': request.user.role
        })


class UserListCreateView(generics.ListCreateAPIView):

    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer

        return UserListSerializer

class UserDetailView(generics.RetrieveUpdateAPIView):

    queryset = User.objects.all()
    permission_classes = [IsAdmin]
    serializer_class = UserUpdateSerializer


class UserDeactivateView(APIView):

    permission_classes = [IsAdmin]

    def patch(self, request, pk):

        try:
            user = User.objects.get(pk=pk)
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

        if user.is_superuser and not request.user.is_superuser:
            return Response(
                {'error': 'Only a superuser can deactivate this account.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user.is_active = False
        user.save(update_fields=['is_active'])

        return Response(
            {'message': 'User successfully deactivated.'},
            status=status.HTTP_200_OK
        )