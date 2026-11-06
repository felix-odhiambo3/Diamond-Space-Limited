
from django.contrib import admin
from .models import Customer, Vehicle, CreditAccount

from .models import (
    Customer,
    Vehicle,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'phone_number',
        'email',
        'is_active',
    )
    search_fields = ('full_name', 'phone_number', 'email')
    list_filter = ('is_active',)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'registration_number',
        'vehicle_type',
        'customer',
        'branch',
        'is_active',
    )
    search_fields = (
        'registration_number',
        'customer__full_name',
        'customer__phone_number',
    )
    list_filter = (
        'vehicle_type',
        'branch',
        'is_active',
    )


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = (
        'account_number',
        'customer',
        'credit_limit',
        'payment_terms_days',
        'status',
        'approved_by',
        'approved_at',
    )
    search_fields = (
        'account_number',
        'customer__full_name',
        'customer__phone_number',
    )
    list_filter = (
        'status',
        'payment_terms_days',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'status',
'approved_by',
'approved_at',
    )



@admin.register(CreditLedgerEntry)
class CreditLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'account',
        'entry_type',
        'amount',
        'due_date',
        'created_by',
        'created_at',
    )

    list_filter = (
        'entry_type',
        'created_at',
    )

    search_fields = (
        'account__account_number',
        'account__customer__full_name',
        'idempotency_key',
        'reference_id',
    )

    readonly_fields = [
        field.name for field in CreditLedgerEntry._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditPaymentAllocation)
class CreditPaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'payment_entry',
        'charge_entry',
        'amount',
        'allocated_by',
        'created_at',
    )

    readonly_fields = [
        field.name for field in CreditPaymentAllocation._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

