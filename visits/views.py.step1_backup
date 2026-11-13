
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin, IsSupervisor, IsDetailer

from .models import Visit, VisitService, ServiceAssignment
from .serializers import (
    VisitSerializer,
    VisitServiceSerializer,
    ServiceAssignmentSerializer,
    ServiceAssignmentRemovalSerializer,
)


class VisitListCreateView(generics.ListCreateAPIView):
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Visit.objects.select_related(
            'vehicle',
            'branch',
            'checked_in_by',
        )

        if user.is_superuser or user.role in ['ADMIN', 'OWNER']:
            return queryset.all()

        if hasattr(user, 'staff_profile'):
            return queryset.filter(
                branch=user.staff_profile.branch
            )

        return queryset.none()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor | IsDetailer)(),
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
            'checked_in_by',
        )

        if user.is_superuser or user.role in ['ADMIN', 'OWNER']:
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
        user = self.request.user

        queryset = Visit.objects.all()

        if not user.is_superuser and user.role not in ['ADMIN', 'OWNER']:
            if not hasattr(user, 'staff_profile'):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(
                    branch=user.staff_profile.branch
                )

        return get_object_or_404(
            queryset,
            pk=self.kwargs['visit_id'],
        )

    def get_queryset(self):
        visit = self.get_visit()

        return VisitService.objects.filter(
            visit=visit
        ).select_related(
            'service',
            'added_by',
        )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor | IsDetailer)(),
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
            Visit.Status.CANCELLED,
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
            'service',
        ).filter(
            visit_id=self.kwargs['visit_id'],
            pk=self.kwargs['visit_service_id'],
        )

        if not user.is_superuser and user.role not in ['ADMIN', 'OWNER']:
            if not hasattr(user, 'staff_profile'):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(
                    visit__branch=user.staff_profile.branch
                )

        return get_object_or_404(queryset)

    def get_queryset(self):
        visit_service = self.get_visit_service()

        return ServiceAssignment.objects.filter(
            visit_service=visit_service
        ).select_related(
            'staff',
            'staff__user',
            'assigned_by',
            'removed_by',
        )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                IsAuthenticated(),
                (IsAdmin | IsSupervisor)(),
            ]

        return super().get_permissions()

    def perform_create(self, serializer):
        visit_service = self.get_visit_service()
        visit = visit_service.visit
        staff = serializer.validated_data['staff']
        user = self.request.user

        # Do not assign staff to a closed visit.
        if visit.status in [
            Visit.Status.COMPLETED,
            Visit.Status.CANCELLED,
        ]:
            raise ValidationError(
                "Staff cannot be assigned to a completed or cancelled visit."
            )

        # Ensure the staff member is currently employed.
        if staff.employment_status != staff.EmploymentStatus.ACTIVE:
            raise ValidationError(
                "Inactive or suspended staff cannot be assigned."
            )

        if not staff.user.is_active:
            raise ValidationError(
                "This staff member's user account is inactive."
            )

        # Staff must belong to the same branch as the visit.
        if staff.branch_id != visit.branch_id:
            raise ValidationError(
                "Staff can only be assigned to visits at their own branch."
            )

        # Car wash services require cleaners.
        # Detailing services require detailers.
        if visit_service.service_category == 'CAR_WASH':
            expected_role = 'CLEANER'
        elif visit_service.service_category == 'DETAILING':
            expected_role = 'DETAILER'
        else:
            raise ValidationError(
                "The service category does not support staff assignment."
            )

        if staff.user.role != expected_role:
            raise ValidationError(
                f"Only staff with the {expected_role} role can be assigned "
                f"to this service."
            )

        # Prevent duplicate active assignments.
        already_assigned = ServiceAssignment.objects.filter(
            visit_service=visit_service,
            staff=staff,
            is_active=True,
        ).exists()

        if already_assigned:
            raise ValidationError(
                "This staff member is already assigned to this service."
            )

        serializer.save(
            visit_service=visit_service,
            assigned_by=user,
        )


class ServiceAssignmentRemoveView(generics.GenericAPIView):
    serializer_class = ServiceAssignmentRemovalSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [
            IsAuthenticated(),
            (IsAdmin | IsSupervisor)(),
        ]

    def post(self, request, visit_id, visit_service_id, assignment_id):
        user = request.user

        queryset = VisitService.objects.select_related(
            'visit'
        ).filter(
            pk=visit_service_id,
            visit_id=visit_id,
        )

        # Restrict supervisors to their own branch.
        if not user.is_superuser and user.role not in ['ADMIN', 'OWNER']:
            if not hasattr(user, 'staff_profile'):
                raise ValidationError(
                    "You do not have permission to remove this assignment."
                )

            queryset = queryset.filter(
                visit__branch=user.staff_profile.branch
            )

        visit_service = get_object_or_404(queryset)

        assignment = get_object_or_404(
            ServiceAssignment,
            pk=assignment_id,
            visit_service=visit_service,
            is_active=True,
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Soft removal preserves the assignment history.
        assignment.is_active = False
        assignment.removed_at = timezone.now()
        assignment.removed_by = user
        assignment.removal_reason = serializer.validated_data[
            'removal_reason'
        ]

        assignment.save(update_fields=[
            'is_active',
            'removed_at',
            'removed_by',
            'removal_reason',
        ])

        return Response(
            ServiceAssignmentSerializer(assignment).data,
            status=status.HTTP_200_OK,
        )
