from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from rest_framework import serializers

from .models import (
    StaffProfile,
    ShiftAssignment,
    StaffStatusHistory,
)
from .services import assign_staff_shift

User = get_user_model()


class StaffProfileSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source='user.username',
        read_only=True
    )

    email = serializers.EmailField(
        source='user.email',
        read_only=True
    )

    role = serializers.CharField(
        source='user.role',
        read_only=True
    )

    full_name = serializers.SerializerMethodField()

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    current_shift = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile

        fields = [
            'id',
            'user',
            'username',
            'email',
            'role',
            'full_name',
            'staff_number',
            'branch',
            'branch_name',
            'phone_number',
            'employment_status',
            'date_joined',
            'current_shift',
            'is_archived',
            'archived_at',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'user',
            'username',
            'email',
            'role',
            'full_name',
            'branch_name',
            'current_shift',
            'is_archived',
            'archived_at',
            'created_at',
            'updated_at',
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name()

    def get_current_shift(self, obj):
        today = timezone.localdate()

        assignments = obj.shift_assignments.all()

        current_assignments = [
            assignment
            for assignment in assignments
            if (
                assignment.effective_from <= today
                and (
                    assignment.effective_to is None
                    or assignment.effective_to >= today
                )
            )
        ]

        if not current_assignments:
            return None

        current_assignment = max(
            current_assignments,
            key=lambda assignment: assignment.effective_from
        )

        return current_assignment.shift


class ShiftAssignmentSerializer(serializers.ModelSerializer):

    staff_number = serializers.CharField(
        source='staff.staff_number',
        read_only=True
    )

    class Meta:
        model = ShiftAssignment

        fields = [
            'id',
            'staff',
            'staff_number',
            'shift',
            'effective_from',
            'effective_to',
            'changed_by',
            'reason',
            'created_at',
        ]

        read_only_fields = [
            'id',
            'changed_by',
            'created_at',
            'effective_to',
        ]


class StaffStatusActionSerializer(serializers.Serializer):

    action = serializers.ChoiceField(
        choices=[
            ('ACTIVATE', 'Activate'),
            ('DEACTIVATE', 'Deactivate'),
            ('SUSPEND', 'Suspend'),
            ('ARCHIVE', 'Archive'),
        ]
    )

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000
    )

    def validate(self, attrs):
        action = attrs.get('action')
        reason = attrs.get('reason', '').strip()

        if action in ('SUSPEND', 'DEACTIVATE', 'ARCHIVE') and not reason:
            raise serializers.ValidationError({
                'reason': 'A reason is required for this action.'
            })

        attrs['reason'] = reason
        return attrs


class StaffStatusHistorySerializer(serializers.ModelSerializer):

    performed_by_username = serializers.CharField(
        source='performed_by.username',
        read_only=True,
        default=None
    )

    class Meta:
        model = StaffStatusHistory

        fields = [
            'id',
            'action',
            'performed_by',
            'performed_by_username',
            'reason',
            'created_at',
        ]

        read_only_fields = fields


class StaffRegistrationSerializer(serializers.ModelSerializer):

    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    first_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    last_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    role = serializers.ChoiceField(
        choices=[
            ('SUPERVISOR', 'Supervisor'),
            ('ACCOUNTS', 'Accounts'),
            ('CLEANER', 'Cleaner'),
            ('DETAILER', 'Detailer'),
        ]
    )

    shift = serializers.ChoiceField(
        choices=ShiftAssignment.Shift.choices,
        write_only=True
    )

    class Meta:
        model = StaffProfile

        fields = [
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'role',
            'shift',
            'staff_number',
            'branch',
            'phone_number',
            'date_joined',
        ]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return value

    def validate_staff_number(self, value):
        if StaffProfile.objects.filter(
            staff_number=value
        ).exists():
            raise serializers.ValidationError(
                "This staff number already exists."
            )

        return value

    def validate_date_joined(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                "Date joined cannot be in the future."
            )

        return value

    def create(self, validated_data):
        shift = validated_data.pop('shift')

        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name', ''),
            'last_name': validated_data.pop('last_name', ''),
            'role': validated_data.pop('role'),
        }

        request = self.context.get('request')

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "An authenticated administrator is required."
            )

        with transaction.atomic():
            user = User.objects.create_user(**user_data)

            staff = StaffProfile.objects.create(
                user=user,
                **validated_data
            )

            try:
                assign_staff_shift(
                    staff_id=staff.pk,
                    shift=shift,
                    effective_from=timezone.localdate(),
                    changed_by=request.user,
                    reason=(
                        'Initial shift assignment during '
                        'staff registration.'
                    ),
                )

            except DjangoValidationError as error:
                raise serializers.ValidationError(error.messages)

        return staff

    def to_representation(self, instance):
        return StaffProfileSerializer(
            instance,
            context=self.context
        ).data


class ShiftChangeSerializer(serializers.Serializer):

    shift = serializers.ChoiceField(
        choices=ShiftAssignment.Shift.choices
    )

    effective_from = serializers.DateField()

    reason = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate_effective_from(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(
                "Shift changes cannot be backdated."
            )

        return value