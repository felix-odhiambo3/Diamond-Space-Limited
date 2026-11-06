
from rest_framework import serializers

from .models import Visit
from vehicles.models import Vehicle
from .models import ServiceAssignment
from staff.models import StaffProfile


class VisitSerializer(serializers.ModelSerializer):
    vehicle_registration = serializers.CharField(
        source='vehicle.registration_number',
        read_only=True
    )

    checked_in_by_name = serializers.CharField(
        source='checked_in_by.get_full_name',
        read_only=True
    )

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    class Meta:
        model = Visit
        fields = [
            'id',
            'vehicle',
            'vehicle_registration',
            'branch',
            'branch_name',
            'checked_in_by',
            'checked_in_by_name',
            'status',
            'arrival_time',
            'completed_at',
            'notes',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'branch',
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

    def create(self, validated_data):
        request = self.context['request']
        vehicle = validated_data['vehicle']

        validated_data['checked_in_by'] = request.user
        validated_data['branch'] = vehicle.branch

        return super().create(validated_data)


from .models import VisitService


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