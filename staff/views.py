from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import StaffRegistrationSerializer

from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError
from .services import assign_staff_shift
from .serializers import ShiftChangeSerializer

from .models import StaffProfile, ShiftAssignment
from .serializers import (
    StaffProfileSerializer,
    ShiftAssignmentSerializer,
)
from accounts.permissions import IsAdmin

from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError
from .services import assign_staff_shift
from .serializers import ShiftChangeSerializer


class StaffListCreateView(generics.ListCreateAPIView):

    queryset = StaffProfile.objects.select_related(
        'user', 'branch'
    ).all()

    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StaffRegistrationSerializer

        return StaffProfileSerializer


class StaffDetailView(generics.RetrieveUpdateAPIView):

    queryset = StaffProfile.objects.select_related(
        'user', 'branch'
    ).all()

    serializer_class = StaffProfileSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class StaffShiftHistoryView(generics.ListAPIView):

    serializer_class = ShiftAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return ShiftAssignment.objects.filter(
            staff_id=self.kwargs['staff_id']
        ).select_related(
            'staff', 'changed_by'
        )

class StaffShiftChangeView(generics.GenericAPIView):

    serializer_class = ShiftChangeSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, staff_id):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = assign_staff_shift(
                staff_id=staff_id,
                shift=serializer.validated_data['shift'],
                effective_from=serializer.validated_data['effective_from'],
                changed_by=request.user,
                reason=serializer.validated_data.get('reason', '')
            )

        except StaffProfile.DoesNotExist:
            return Response(
                {'detail': 'Staff member not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        except ValidationError as error:
            raise DRFValidationError(error.messages)

        return Response(
            ShiftAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED
        )

class StaffShiftChangeView(generics.GenericAPIView):

    serializer_class = ShiftChangeSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, staff_id):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = assign_staff_shift(
                staff_id=staff_id,
                shift=serializer.validated_data['shift'],
                effective_from=serializer.validated_data['effective_from'],
                changed_by=request.user,
                reason=serializer.validated_data.get('reason', '')
            )

        except StaffProfile.DoesNotExist:
            return Response(
                {'detail': 'Staff member not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        except ValidationError as error:
            raise DRFValidationError(error.messages)

        return Response(
            ShiftAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED
        )