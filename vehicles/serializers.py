
from decimal import Decimal

from rest_framework import serializers

from .models import (
    Customer,
    Vehicle,
    VehicleCategory,
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


class VehicleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCategory
        fields = [
            'id',
            'name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]

    def validate_name(self, value):
        value = ' '.join(value.strip().split())

        if not value:
            raise serializers.ValidationError(
                'Category name is required.'
            )

        return value


class VehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source='customer.full_name',
        read_only=True
    )

    branch_name = serializers.CharField(
        source='branch.name',
        read_only=True
    )

    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )

    make_model = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=100
    )

    category = serializers.PrimaryKeyRelatedField(
        queryset=VehicleCategory.objects.filter(is_active=True),
        required=True
    )

    # Kept writable temporarily for compatibility with older clients.
    # If omitted, it is derived from the selected category.
    vehicle_type = serializers.ChoiceField(
        choices=Vehicle.VehicleType.choices,
        required=False
    )

    class Meta:
        model = Vehicle
        fields = [
            'id',
            'registration_number',
            'make_model',
            'category',
            'category_name',
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
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]

    def validate_registration_number(self, value):
        normalized = ''.join(value.split()).upper()

        if not normalized:
            raise serializers.ValidationError(
                'Vehicle registration number is required.'
            )

        vehicles = Vehicle.objects.all()

        if self.instance is not None:
            vehicles = vehicles.exclude(pk=self.instance.pk)

        for vehicle in vehicles.only('pk', 'registration_number').iterator():
            existing_normalized = ''.join(
                vehicle.registration_number.split()
            ).upper()

            if existing_normalized == normalized:
                raise serializers.ValidationError(
                    'A vehicle with this registration number already exists.'
                )

        return normalized

    def validate_make_model(self, value):
        value = ' '.join(value.strip().split())

        if not value:
            raise serializers.ValidationError(
                'Vehicle make/model is required.'
            )

        return value

    def validate(self, attrs):
        category = attrs.get(
            'category',
            getattr(self.instance, 'category', None)
        )

        if category is None:
            raise serializers.ValidationError({
                'category': 'Vehicle category is required.'
            })

        # Keep the old field consistent with the new category.
        category_mapping = {
            'saloon': Vehicle.VehicleType.SALOON,
            'suv': Vehicle.VehicleType.SUV,
            'pickup': Vehicle.VehicleType.PICKUP,
            'van': Vehicle.VehicleType.VAN,
            'truck': Vehicle.VehicleType.TRUCK,
            'motorcycle': Vehicle.VehicleType.MOTORCYCLE,
        }

        derived_vehicle_type = category_mapping.get(
            category.name.strip().casefold(),
            Vehicle.VehicleType.OTHER
        )

        attrs['vehicle_type'] = derived_vehicle_type

        return attrs


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
