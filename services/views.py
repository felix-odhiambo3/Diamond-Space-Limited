from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Service
from .serializers import ServiceSerializer
from accounts.permissions import IsAdmin


class ServiceListCreateView(generics.ListCreateAPIView):

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Service.objects.all()

        if self.request.user.role != 'ADMIN' and not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdmin()]

        return super().get_permissions()


class ServiceDetailView(generics.RetrieveUpdateAPIView):

    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, IsAdmin]