from rest_framework import serializers
from .models import StaffProfile
from accounts.models import User


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

    class Meta:
        model = StaffProfile
        fields = [
            'id',
            'user',
            'username',
            'email',
            'role',
            'staff_number',
            'branch',
            'phone_number',
            'employment_status',
            'date_joined',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]

    def validate_user(self, user):
        if StaffProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "This user already has a staff profile."
            )

        if user.role == User.Role.ADMIN:
            raise serializers.ValidationError(
                "Administrator accounts cannot be registered as ordinary staff."
            )

        return user

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import StaffProfile, ShiftAssignment

User = get_user_model()


class StaffProfileSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source='user.username',
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
        required=False
    )

    last_name = serializers.CharField(
        write_only=True,
        required=False
    )

    role = serializers.ChoiceField(
        choices=User.Role.choices
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
        if User.objects.filter(email=value).exists():
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

    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name', ''),
            'last_name': validated_data.pop('last_name', ''),
            'role': validated_data.pop('role'),
        }

        from django.db import transaction

        with transaction.atomic():
            user = User.objects.create_user(**user_data)

            staff = StaffProfile.objects.create(
                user=user,
                **validated_data
            )

        return staff

from datetime import date


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
        if value < date.today():
            raise serializers.ValidationError(
                "Shift changes cannot be backdated."
            )

        return value

from datetime import date


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
        if value < date.today():
            raise serializers.ValidationError(
                "Shift changes cannot be backdated."
            )

        return value