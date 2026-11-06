from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Branch
from .serializers import BranchSerializer
from accounts.permissions import IsAdmin


class BranchListCreateView(generics.ListCreateAPIView):

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class BranchDetailView(generics.RetrieveUpdateAPIView):

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsAdmin]