
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from rest_framework import serializers

from .models import StaffProfile, ShiftAssignment
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
            'created_at',
            'updated_at',
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name()


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

    # Validate username uniqueness
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    # Validate email uniqueness
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return value

    # Validate staff number uniqueness
    def validate_staff_number(self, value):
        if StaffProfile.objects.filter(
            staff_number=value
        ).exists():
            raise serializers.ValidationError(
                "This staff number already exists."
            )

        return value

    # Prevent future employment joining dates
    def validate_date_joined(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                "Date joined cannot be in the future."
            )

        return value

    # Create user, staff profile and initial shift assignment
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

    # Return the standard staff representation after registration
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
