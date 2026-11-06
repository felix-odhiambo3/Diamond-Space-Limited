
from django.conf import settings
from django.db import models
from branches.models import Branch
from decimal import Decimal
from django.db.models import Sum, Q


class Customer(models.Model):
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class Vehicle(models.Model):

    class VehicleType(models.TextChoices):
        SALOON = 'SALOON', 'Saloon'
        SUV = 'SUV', 'SUV'
        PICKUP = 'PICKUP', 'Pickup'
        VAN = 'VAN', 'Van'
        TRUCK = 'TRUCK', 'Truck'
        MOTORCYCLE = 'MOTORCYCLE', 'Motorcycle'
        OTHER = 'OTHER', 'Other'

    registration_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='vehicles',
        null=True,
        blank=True
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='vehicles'
    )

    no_plastic_mat = models.TextField(
        blank=True,
        help_text="Optional instructions concerning plastic mats."
    )

    no_woolen_mat = models.TextField(
        blank=True,
        help_text="Optional instructions concerning woolen mats."
    )

    special_concerns = models.TextField(
        blank=True,
        help_text="Optional special instructions or concerns about this vehicle."
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration_number']

    def __str__(self):
        return self.registration_number


class CreditAccount(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        CLOSED = 'CLOSED', 'Closed'

    customer = models.OneToOneField(
        Customer,
        on_delete=models.PROTECT,
        related_name='credit_account'
    )

    account_number = models.CharField(max_length=30, unique=True)

    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    payment_terms_days = models.PositiveSmallIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_credit_accounts'
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def outstanding_balance(self):
        totals = self.ledger_entries.aggregate(
            charges=Sum(
                'amount',
                filter=Q(entry_type='CHARGE')
            ),
            payments=Sum(
                'amount',
                filter=Q(entry_type='PAYMENT')
            )
        )

        charges = totals['charges'] or Decimal('0.00')
        payments = totals['payments'] or Decimal('0.00')

        return charges - payments

    @property
    def available_credit(self):
        if self.credit_limit is None:
            return None

        return self.credit_limit - self.outstanding_balance

    class Meta:
        ordering = ['account_number']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(credit_limit__isnull=True) |
                models.Q(credit_limit__gt=0),
                name='credit_limit_null_or_positive'
            )
        ]

    @property
    def is_unlimited(self):
        return self.credit_limit is None

    def __str__(self):
        return f"{self.account_number} - {self.customer.full_name}"



class CreditLedgerEntry(models.Model):

    class EntryType(models.TextChoices):
        CHARGE = 'CHARGE', 'Credit Charge'
        PAYMENT = 'PAYMENT', 'Payment Received'

    account = models.ForeignKey(
        CreditAccount,
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )

    entry_type = models.CharField(
        max_length=10,
        choices=EntryType.choices
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    description = models.CharField(max_length=255)

    # Reference to the originating visit or payment.
    reference_type = models.CharField(
        max_length=30,
        blank=True
    )

    reference_id = models.CharField(
        max_length=64,
        blank=True
    )

    # Prevents duplicate financial transactions.
    idempotency_key = models.CharField(
        max_length=100,
        unique=True
    )

    due_date = models.DateField(
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='credit_ledger_entries'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='credit_ledger_amount_positive'
            )
        ]

    def __str__(self):
        return (
            f"{self.account.account_number} - "
            f"{self.entry_type} - KES {self.amount}"
        )


class CreditPaymentAllocation(models.Model):

    payment_entry = models.ForeignKey(
        CreditLedgerEntry,
        on_delete=models.PROTECT,
        related_name='payment_allocations'
    )

    charge_entry = models.ForeignKey(
        CreditLedgerEntry,
        on_delete=models.PROTECT,
        related_name='charge_allocations'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    allocated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='credit_payment_allocations'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['payment_entry', 'charge_entry'],
                name='unique_credit_payment_allocation'
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='credit_allocation_amount_positive'
            )
        ]

    def __str__(self):
        return (
            f"Payment #{self.payment_entry_id} allocated "
            f"KES {self.amount} to charge #{self.charge_entry_id}"
        )
