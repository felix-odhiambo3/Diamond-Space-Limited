
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Service
from .serializers import ServiceSerializer
from accounts.permissions import IsAdminOrOwner


class ServiceListCreateView(generics.ListCreateAPIView):

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Service.objects.all()

        if (
            not user.is_superuser
            and user.role not in ['ADMIN', 'OWNER']
        ):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                IsAdminOrOwner(),
            ]

        return super().get_permissions()


class ServiceDetailView(generics.RetrieveUpdateAPIView):

    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwner]
