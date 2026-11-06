
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Visit
from .serializers import VisitSerializer
from accounts.permissions import (
    IsAdmin,
    IsSupervisor,
    IsDetailer,
)

from rest_framework.exceptions import ValidationError
from .models import VisitService
from .serializers import VisitServiceSerializer
from services.models import Service
from staff.models import StaffProfile

from django.utils import timezone
from rest_framework.response import Response

from .serializers import ServiceAssignmentRemovalSerializer

from django.shortcuts import get_object_or_404

from .models import ServiceAssignment
from .serializers import ServiceAssignmentSerializer

class VisitListCreateView(generics.ListCreateAPIView):
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Visit.objects.select_related(
            'vehicle',
            'branch',
            'checked_in_by'
        ).all()

        if user.role == 'ADMIN' or user.is_superuser:
            return queryset

        if user.role == 'OWNER':
            return queryset

        # Other staff initially see visits from their assigned branch.
        if hasattr(user, 'staff_profile'):
            return queryset.filter(
                branch=user.staff_profile.branch
            )

        return queryset.none()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor | IsDetailer)()
            ]

        return super().get_permissions()


class VisitDetailView(generics.RetrieveAPIView):
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Visit.objects.select_related(
            'vehicle',
            'branch',
            'checked_in_by'
        )

        if user.role in ['ADMIN', 'OWNER'] or user.is_superuser:
            return queryset.all()

        if hasattr(user, 'staff_profile'):
            return queryset.filter(
                branch=user.staff_profile.branch
            )

        return queryset.none()


class VisitServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = VisitServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_visit(self):
        return generics.get_object_or_404(
            Visit,
            pk=self.kwargs['visit_id']
        )

    def get_queryset(self):
        visit = self.get_visit()
        user = self.request.user

        queryset = VisitService.objects.filter(
            visit=visit
        ).select_related('service', 'added_by')

        if user.role in ['ADMIN', 'OWNER'] or user.is_superuser:
            return queryset

        if hasattr(user, 'staff_profile'):
            if user.staff_profile.branch_id == visit.branch_id:
                return queryset

        return queryset.none()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor | IsDetailer)()
            ]

        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['visit'] = self.get_visit()
        return context

    def perform_create(self, serializer):
        visit = self.get_visit()

        if visit.status in [
            Visit.Status.COMPLETED,
            Visit.Status.CANCELLED
        ]:
            raise ValidationError(
                "Services cannot be added to a completed or cancelled visit."
            )

        serializer.save()

class ServiceAssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = ServiceAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_visit_service(self):
        user = self.request.user

        queryset = VisitService.objects.select_related(
            'visit',
            'service'
        ).filter(
            visit_id=self.kwargs['visit_id']
        )

        if user.role not in ['ADMIN', 'OWNER'] and not user.is_superuser:
            if hasattr(user, 'staff_profile'):
                queryset = queryset.filter(
                    visit__branch=user.staff_profile.branch
                )
            else:
                queryset = queryset.none()

        return get_object_or_404(
            queryset,
            pk=self.kwargs['visit_service_id']
        )

    def get_queryset(self):
        visit_service = self.get_visit_service()

        return ServiceAssignment.objects.filter(
            visit_service=visit_service
        ).select_related(
            'staff__user',
            'assigned_by'
        )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor)()
            ]

        return super().get_permissions()

    def perform_create(self, serializer):
        visit_service = self.get_visit_service()
        visit = visit_service.visit
        staff = serializer.validated_data['staff']

        if visit.status in [
            Visit.Status.COMPLETED,
            Visit.Status.CANCELLED
        ]:
            raise ValidationError(
                "Cannot assign staff to a completed or cancelled visit."
            )

        if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
            raise ValidationError(
                "This staff member is not currently active."
            )

        if not staff.user.is_active:
            raise ValidationError(
                "This staff member's user account is inactive."
            )

        if staff.branch_id != visit.branch_id:
            raise ValidationError(
                "Staff can only be assigned to services at their own branch."
            )

        if visit_service.service_category == 'DETAILING':
            expected_role = 'DETAILER'
        else:
            expected_role = 'CLEANER'

        if staff.user.role != expected_role:
            raise ValidationError(
                f"Only {expected_role.lower()} staff can be assigned to this service."
            )

        if ServiceAssignment.objects.filter(
            visit_service=visit_service,
            staff=staff,
            is_active=True
        ).exists():
            raise ValidationError(
                "This staff member is already assigned to this service."
            )

        serializer.save(
            visit_service=visit_service,
            assigned_by=self.request.user
        )


class ServiceAssignmentRemoveView(generics.GenericAPIView):
    serializer_class = ServiceAssignmentRemovalSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [
            IsAuthenticated(),
            (IsAdmin | IsSupervisor)()
        ]

    def post(self, request, visit_id, visit_service_id, assignment_id):
        visit_service = get_object_or_404(
            VisitService.objects.select_related('visit'),
            pk=visit_service_id,
            visit_id=visit_id
        )

        user = request.user

        if not user.is_superuser and user.role != 'ADMIN':
            if not hasattr(user, 'staff_profile'):
                raise ValidationError(
                    "You do not have permission to remove this assignment."
                )

            if user.staff_profile.branch_id != visit_service.visit.branch_id:
                raise ValidationError(
                    "You can only remove assignments at your own branch."
                )

        assignment = get_object_or_404(
            ServiceAssignment,
            pk=assignment_id,
            visit_service=visit_service,
            is_active=True
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment.is_active = False
        assignment.removed_at = timezone.now()
        assignment.removed_by = user
        assignment.removal_reason = serializer.validated_data['removal_reason']

        assignment.save(update_fields=[
            'is_active',
            'removed_at',
            'removed_by',
            'removal_reason',
        ])

        return Response(
            ServiceAssignmentSerializer(assignment).data,
            status=200
        )