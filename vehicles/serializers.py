
from decimal import Decimal

from rest_framework import serializers

from .models import (
    Customer,
    Vehicle,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id',
            'full_name',
            'phone_number',
            'email',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source='customer.full_name',
        read_only=True
    )

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    class Meta:
        model = Vehicle
        fields = [
            'id',
            'registration_number',
            'vehicle_type',
            'customer',
            'customer_name',
            'branch',
            'branch_name',
            'no_plastic_mat',
            'no_woolen_mat',
            'special_concerns',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_registration_number(self, value):
        return value.strip().upper()


class CreditAccountSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source='customer.full_name',
        read_only=True
    )

    customer_phone = serializers.CharField(
        source='customer.phone_number',
        read_only=True
    )

    is_unlimited = serializers.BooleanField(read_only=True)

    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = CreditAccount
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_phone',
            'account_number',
            'credit_limit',
            'is_unlimited',
            'payment_terms_days',
            'status',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'status',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'created_at',
            'updated_at',
        ]

    def validate_customer(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "An inactive customer cannot have a credit account."
            )

        existing_account = getattr(value, 'credit_account', None)

        if (
            existing_account is not None
            and (
                self.instance is None
                or existing_account.pk != self.instance.pk
            )
        ):
            raise serializers.ValidationError(
                "This customer already has a credit account."
            )

        return value

    def validate_account_number(self, value):
        return value.strip().upper()

    def validate_payment_terms_days(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Payment terms must be at least one day."
            )

        return value


class CreditLedgerEntrySerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(
        source='account.account_number',
        read_only=True
    )

    created_by_name = serializers.CharField(
        source='created_by.username',
        read_only=True
    )

    class Meta:
        model = CreditLedgerEntry
        fields = [
            'id',
            'account',
            'account_number',
            'entry_type',
            'amount',
            'description',
            'reference_type',
            'reference_id',
            'idempotency_key',
            'due_date',
            'created_by',
            'created_by_name',
            'created_at',
        ]
        read_only_fields = fields


class CreditPaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPaymentAllocation
        fields = [
            'id',
            'payment_entry',
            'charge_entry',
            'amount',
            'allocated_by',
            'created_at',
        ]
        read_only_fields = fields


class CreditPaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )

    description = serializers.CharField(max_length=255)

    idempotency_key = serializers.CharField(max_length=100)

    reference_type = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True
    )

    reference_id = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True
    )

    def validate_idempotency_key(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'An idempotency key is required.'
            )

        return value
