
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .models import Visit, VisitService, ServiceAssignment
from branches.models import Branch
from vehicles.models import Vehicle


class VisitSerializer(serializers.ModelSerializer):
    vehicle_registration = serializers.CharField(
        source='vehicle.registration_number',
        read_only=True
    )

    vehicle_make_model = serializers.CharField(
        source='vehicle.make_model',
        read_only=True
    )

    vehicle_category = serializers.CharField(
        source='vehicle.category.name',
        read_only=True
    )

    checked_in_by_name = serializers.CharField(
        source='checked_in_by.get_full_name',
        read_only=True
    )

    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        required=False
    )

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    plastic_mat_count = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0
    )

    woolen_mat_count = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0
    )

    class Meta:
        model = Visit
        fields = [
            'id',
            'vehicle',
            'vehicle_registration',
            'vehicle_make_model',
            'vehicle_category',
            'branch',
            'branch_name',
            'checked_in_by',
            'checked_in_by_name',
            'status',
            'arrival_time',
            'completed_at',
            'plastic_mat_count',
            'woolen_mat_count',
            'comment',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'checked_in_by',
            'status',
            'arrival_time',
            'completed_at',
            'created_at',
            'updated_at',
        ]

    def validate_vehicle(self, vehicle):
        if not vehicle.is_active:
            raise serializers.ValidationError(
                "This vehicle is inactive and cannot be checked in."
            )

        return vehicle

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        selected_branch = attrs.get('branch')

        # Administrators and Owners may select an active
        # servicing branch.
        if user.is_superuser or user.role in ['ADMIN', 'OWNER']:
            if selected_branch is None:
                raise serializers.ValidationError({
                    'branch': (
                        'Select the branch where the vehicle '
                        'will actually be serviced.'
                    )
                })

            return attrs

        # Other permitted users must have a staff profile.
        if not hasattr(user, 'staff_profile'):
            raise PermissionDenied(
                "Your account is not assigned to a branch."
            )

        assigned_branch = user.staff_profile.branch

        if not assigned_branch.is_active:
            raise PermissionDenied(
                "Your assigned branch is inactive."
            )

        # Prevent staff from selecting another branch.
        if (
            selected_branch is not None
            and selected_branch.pk != assigned_branch.pk
        ):
            raise PermissionDenied(
                "You can only create visits at your assigned branch."
            )

        # Automatically use the employee's assigned branch.
        attrs['branch'] = assigned_branch

        return attrs

    def create(self, validated_data):
        request = self.context['request']

        validated_data['checked_in_by'] = request.user

        # The branch comes from validated servicing-branch
        # selection, never from Vehicle.branch.
        return super().create(validated_data)


class VisitServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(read_only=True)
    service_code = serializers.CharField(read_only=True)

    original_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    added_by_name = serializers.CharField(
        source='added_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = VisitService
        fields = [
            'id',
            'visit',
            'service',
            'service_name',
            'service_code',
            'service_category',
            'original_price',
            'duration_minutes',
            'requires_timer',
            'added_by',
            'added_by_name',
            'added_at',
            'is_removed',
        ]

        read_only_fields = [
            'id',
            'visit',
            'service_name',
            'service_code',
            'service_category',
            'original_price',
            'duration_minutes',
            'requires_timer',
            'added_by',
            'added_at',
            'is_removed',
        ]

    def validate_service(self, service):
        if not service.is_active:
            raise serializers.ValidationError(
                "This service is currently inactive."
            )

        return service

    def create(self, validated_data):
        service = validated_data['service']
        request = self.context['request']
        visit = self.context['visit']

        return VisitService.objects.create(
            visit=visit,
            service=service,
            service_name=service.name,
            service_code=service.code,
            service_category=service.category,
            original_price=service.price,
            duration_minutes=service.duration_minutes,
            requires_timer=service.requires_timer,
            added_by=request.user,
        )


class ServiceAssignmentSerializer(serializers.ModelSerializer):
    staff_number = serializers.CharField(
        source='staff.staff_number',
        read_only=True
    )

    staff_name = serializers.CharField(
        source='staff.user.get_full_name',
        read_only=True
    )

    assigned_by_name = serializers.CharField(
        source='assigned_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = ServiceAssignment
        fields = [
            'id',
            'visit_service',
            'staff',
            'staff_number',
            'staff_name',
            'assigned_by',
            'assigned_by_name',
            'assigned_at',
            'is_active',
            'removed_at',
            'removed_by',
            'removal_reason',
        ]

        read_only_fields = [
            'id',
            'visit_service',
            'assigned_by',
            'assigned_at',
            'is_active',
            'removed_at',
            'removed_by',
            'removal_reason',
        ]


class ServiceAssignmentRemovalSerializer(serializers.Serializer):
    removal_reason = serializers.CharField(
        required=True,
        allow_blank=False
    )
