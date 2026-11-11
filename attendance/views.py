
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AttendanceOverrideRequest,
    AttendanceAuditLog,
    ShiftInstance,
)
from .serializers import (
    AttendanceOverrideCreateSerializer,
    AttendanceOverrideReviewSerializer,
    AttendanceOverrideRequestSerializer,
    AttendanceAuditLogSerializer,
)
from .services import (
    AttendanceError,
    create_attendance_override_request,
    review_attendance_override_request,
    execute_attendance_override_request,
)


def get_user_role(user):
    """Return the user's effective role."""
    if user.is_superuser:
        return 'OWNER'

    return getattr(user, 'role', None)


def is_override_manager(user):
    """Check whether a user can manage attendance overrides."""
    return get_user_role(user) in {
        'OWNER',
        'ADMIN',
        'SUPERVISOR',
    }


def get_supervisor_branch(user):
    """Return the supervisor's branch ID."""
    try:
        return user.staff_profile.branch_id
    except AttributeError:
        return None


def get_accessible_override_requests(user):
    """
    Return override requests accessible to the current user.

    Owners and admins can access all branches.
    Supervisors can access requests from their own branch only.
    Other users cannot access override requests.
    """
    queryset = AttendanceOverrideRequest.objects.select_related(
        'attendance',
        'shift_instance',
        'requested_by',
        'reviewed_by',
        'staff__user',
        'branch',
    )

    role = get_user_role(user)

    if role in {'OWNER', 'ADMIN'}:
        return queryset

    if role == 'SUPERVISOR':
        branch_id = get_supervisor_branch(user)

        if branch_id is None:
            return queryset.none()

        return queryset.filter(branch_id=branch_id)

    return queryset.none()


class AttendanceOverrideListCreateView(APIView):
    """List and create assisted attendance override requests."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_override_manager(request.user):
            raise PermissionDenied(
                'You do not have permission to view override requests.'
            )

        queryset = get_accessible_override_requests(request.user)

        request_status = request.query_params.get('status')

        if request_status:
            valid_statuses = {
                'PENDING',
                'APPROVED',
                'REJECTED',
            }

            if request_status not in valid_statuses:
                raise ValidationError({
                    'status': 'Invalid status filter.'
                })

            queryset = queryset.filter(status=request_status)

        serializer = AttendanceOverrideRequestSerializer(
            queryset.order_by('-created_at'),
            many=True,
        )

        return Response(serializer.data)

    def post(self, request):
        if not is_override_manager(request.user):
            raise PermissionDenied(
                'You do not have permission to create override requests.'
            )

        serializer = AttendanceOverrideCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        try:
            override_request = create_attendance_override_request(
                requested_by=request.user,
                **serializer.validated_data,
            )

        except AttendanceError as error:
            raise ValidationError({
                'detail': str(error)
            })

        except DjangoValidationError as error:
            raise ValidationError(error.messages)

        override_request = get_object_or_404(
            get_accessible_override_requests(request.user),
            pk=override_request.pk,
        )

        return Response(
            AttendanceOverrideRequestSerializer(
                override_request,
            ).data,
            status=status.HTTP_201_CREATED,
        )


class AttendanceOverrideDetailView(APIView):
    """Retrieve an individual attendance override request."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not is_override_manager(request.user):
            raise PermissionDenied(
                'You do not have permission to view this request.'
            )

        override_request = get_object_or_404(
            get_accessible_override_requests(request.user),
            pk=pk,
        )

        return Response(
            AttendanceOverrideRequestSerializer(
                override_request,
            ).data,
        )


class AttendanceOverrideReviewView(APIView):
    """Approve or reject an attendance override request."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not is_override_manager(request.user):
            raise PermissionDenied(
                'You do not have permission to review override requests.'
            )

        serializer = AttendanceOverrideReviewSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        try:
            override_request = review_attendance_override_request(
                reviewed_by=request.user,
                request_id=pk,
                decision=serializer.validated_data['decision'],
                reason=serializer.validated_data['reason'],
            )

        except AttendanceError as error:
            raise ValidationError({
                'detail': str(error)
            })

        except AttendanceOverrideRequest.DoesNotExist:
            raise ValidationError({
                'detail': 'Override request not found.'
            })

        override_request = get_object_or_404(
            get_accessible_override_requests(request.user),
            pk=override_request.pk,
        )

        return Response(
            AttendanceOverrideRequestSerializer(
                override_request,
            ).data,
        )


class AttendanceOverrideExecuteView(APIView):
    """Execute an approved assisted attendance action."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not is_override_manager(request.user):
            raise PermissionDenied(
                'You do not have permission to execute override requests.'
            )

        try:
            attendance = execute_attendance_override_request(
                executed_by=request.user,
                request_id=pk,
            )

        except AttendanceError as error:
            raise ValidationError({
                'detail': str(error)
            })

        except AttendanceOverrideRequest.DoesNotExist:
            raise ValidationError({
                'detail': 'Override request not found.'
            })

        return Response({
            'detail': 'Assisted attendance action executed successfully.',
            'attendance_id': attendance.pk,
            'staff_id': attendance.staff_id,
            'shift_instance_id': attendance.shift_instance_id,
            'attendance_status': attendance.attendance_status,
            'checkout_status': attendance.checkout_status,
            'clock_in': attendance.clock_in,
            'clock_out': attendance.clock_out,
            'clock_in_verification': attendance.clock_in_verification,
        })


class AttendanceOverrideAuditView(generics.ListAPIView):
    """Retrieve the audit history for an attendance override request."""

    serializer_class = AttendanceAuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if not is_override_manager(user):
            raise PermissionDenied(
                'You do not have permission to view attendance audit logs.'
            )

        override_request = get_object_or_404(
            get_accessible_override_requests(user),
            pk=self.kwargs['pk'],
        )

        queryset = AttendanceAuditLog.objects.select_related(
            'actor',
            'attendance',
            'shift_instance',
        )

        # Include all audit events associated with the request's
        # attendance record, including execution and shift events.
        if override_request.attendance_id:
            return queryset.filter(
                models.Q(
                    attendance_id=override_request.attendance_id,
                )
                | models.Q(
                    shift_instance_id=override_request.shift_instance_id,
                    action__in=[
                        'OVERRIDE_REQUEST_APPROVED',
                        'OVERRIDE_REQUEST_REJECTED',
                    ],
                    new_values__request_id=override_request.pk,
                )
            ).order_by('created_at')

        # Before execution, include the request's review event.
        return queryset.filter(
            shift_instance_id=override_request.shift_instance_id,
            action__in=[
                'OVERRIDE_REQUEST_APPROVED',
                'OVERRIDE_REQUEST_REJECTED',
            ],
            new_values__request_id=override_request.pk,
        ).order_by('created_at')


class ShiftInstanceListView(generics.ListAPIView):
    """List shift instances accessible to attendance managers."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if not is_override_manager(user):
            raise PermissionDenied(
                'You do not have permission to view shift instances.'
            )

        queryset = ShiftInstance.objects.select_related(
            'branch',
            'configuration',
        ).all()

        role = get_user_role(user)

        # Supervisors can only see shifts belonging to their branch.
        if role == 'SUPERVISOR':
            branch_id = get_supervisor_branch(user)

            if branch_id is None:
                raise PermissionDenied(
                    'Your account is not linked to a branch.'
                )

            queryset = queryset.filter(branch_id=branch_id)

        # Optional filters.
        branch_id = self.request.query_params.get('branch')
        work_date = self.request.query_params.get('work_date')
        shift_status = self.request.query_params.get('status')

        if branch_id:
            if not branch_id.isdigit():
                raise ValidationError({
                    'branch': 'Branch must be a valid numeric ID.'
                })

            queryset = queryset.filter(branch_id=branch_id)

        if work_date:
            from django.utils.dateparse import parse_date

            parsed_date = parse_date(work_date)

            if parsed_date is None:
                raise ValidationError({
                    'work_date': 'Use YYYY-MM-DD format.'
                })

            queryset = queryset.filter(work_date=parsed_date)

        if shift_status:
            valid_statuses = {
                'SCHEDULED',
                'IN_PROGRESS',
                'COMPLETED',
                'FINALIZED',
            }

            if shift_status not in valid_statuses:
                raise ValidationError({
                    'status': 'Invalid shift status.'
                })

            queryset = queryset.filter(status=shift_status)

        return queryset.order_by('-scheduled_start')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        data = [
            {
                'id': shift.id,
                'branch': shift.branch_id,
                'branch_name': shift.branch.name,
                'shift_type': shift.shift_type,
                'work_date': shift.work_date,
                'scheduled_start': shift.scheduled_start,
                'scheduled_end': shift.scheduled_end,
                'status': shift.status,
            }
            for shift in queryset
        ]

        return Response(data)

