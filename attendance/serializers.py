
from rest_framework import serializers

from .models import AttendanceOverrideRequest, AttendanceAuditLog


class AttendanceOverrideCreateSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField(min_value=1)

    shift_instance_id = serializers.IntegerField(min_value=1)

    action = serializers.ChoiceField(
        choices=[
            ('CLOCK_IN', 'Clock in'),
            ('CLOCK_OUT', 'Clock out'),
        ]
    )

    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True
    )

    latitude = serializers.FloatField(
        required=False,
        allow_null=True
    )

    longitude = serializers.FloatField(
        required=False,
        allow_null=True
    )

    accuracy = serializers.FloatField(
        required=False,
        allow_null=True
    )

    def validate(self, attrs):
        gps_fields = [
            attrs.get('latitude'),
            attrs.get('longitude'),
            attrs.get('accuracy'),
        ]

        supplied = [value is not None for value in gps_fields]

        if any(supplied) and not all(supplied):
            raise serializers.ValidationError(
                'Latitude, longitude and accuracy must be '
                'provided together.'
            )

        return attrs


class AttendanceOverrideReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            ('APPROVE', 'Approve'),
            ('REJECT', 'Reject'),
        ]
    )

    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True
    )


class AttendanceOverrideRequestSerializer(serializers.ModelSerializer):
    staff_number = serializers.CharField(
        source='staff.staff_number',
        read_only=True
    )

    staff_username = serializers.CharField(
        source='staff.user.username',
        read_only=True
    )

    staff_full_name = serializers.SerializerMethodField()

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    shift_type = serializers.CharField(
        source='shift_instance.shift_type',
        read_only=True,
        allow_null=True
    )

    work_date = serializers.DateField(
        source='shift_instance.work_date',
        read_only=True,
        allow_null=True
    )

    requested_by_username = serializers.CharField(
        source='requested_by.username',
        read_only=True,
        allow_null=True
    )

    reviewed_by_username = serializers.CharField(
        source='reviewed_by.username',
        read_only=True,
        allow_null=True
    )

    attendance_id = serializers.IntegerField(
        source='attendance.id',
        read_only=True,
        allow_null=True
    )

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    is_executed = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceOverrideRequest

        fields = [
            'id',
            'attendance_id',
            'is_executed',
            'staff',
            'staff_number',
            'staff_username',
            'staff_full_name',
            'branch',
            'branch_name',
            'shift_instance',
            'shift_type',
            'work_date',
            'action',
            'latitude',
            'longitude',
            'accuracy',
            'employee_reason',
            'status',
            'status_display',
            'requested_by',
            'requested_by_username',
            'reviewed_by',
            'reviewed_by_username',
            'reviewer_reason',
            'reviewed_at',
            'created_at',
        ]

        read_only_fields = fields

    def get_staff_full_name(self, obj):
        return obj.staff.user.get_full_name()

    def get_is_executed(self, obj):
        return obj.attendance_id is not None


class AttendanceAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source='actor.username',
        read_only=True
    )

    class Meta:
        model = AttendanceAuditLog

        fields = [
            'id',
            'attendance',
            'shift_instance',
            'action',
            'old_values',
            'new_values',
            'actor',
            'actor_username',
            'reason',
            'created_at',
        ]

        read_only_fields = fields
