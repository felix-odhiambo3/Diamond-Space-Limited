
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CreditAccount, CreditLedgerEntry

from django.db.models import Sum

from .models import (
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)


class CreditLedgerError(Exception):
    """Raised when a credit ledger operation violates a business rule."""
    pass


@transaction.atomic
def create_credit_charge(
    *,
    account_id,
    amount,
    description,
    idempotency_key,
    created_by,
    reference_type='',
    reference_id='',
):
    """
    Record a new charge against an active customer credit account.
    """

    # Validate amount.
    try:
        amount = Decimal(str(amount))
    except Exception:
        raise CreditLedgerError('Invalid charge amount.')

    if not amount.is_finite() or amount <= Decimal('0.00'):
        raise CreditLedgerError('Charge amount must be greater than zero.')

    if amount.quantize(Decimal('0.01')) != amount:
        raise CreditLedgerError('Charge amount cannot have more than two decimal places.')

    if not idempotency_key or len(idempotency_key) > 100:
        raise CreditLedgerError('A valid idempotency key is required.')

    # Lock the account to prevent simultaneous charges exceeding its limit.
    try:
        account = CreditAccount.objects.select_for_update().get(
            pk=account_id
        )
    except CreditAccount.DoesNotExist:
        raise CreditLedgerError('Credit account does not exist.')

    # Check for an existing transaction.
    existing = CreditLedgerEntry.objects.filter(
        idempotency_key=idempotency_key
    ).first()

    if existing:
        if (
            existing.account_id == account.id
            and existing.entry_type == CreditLedgerEntry.EntryType.CHARGE
            and existing.amount == amount
        ):
            return existing

        raise CreditLedgerError(
            'This idempotency key has already been used.'
        )

    if account.status != CreditAccount.Status.ACTIVE:
        raise CreditLedgerError(
            'Only active credit accounts can receive new charges.'
        )

    if not account.customer.is_active:
        raise CreditLedgerError(
            'The customer associated with this account is inactive.'
        )

    if account.credit_limit is not None:
        if account.outstanding_balance + amount > account.credit_limit:
            raise CreditLedgerError(
                'This charge exceeds the customer credit limit.'
            )

    due_date = (
        timezone.localdate()
        + timedelta(days=account.payment_terms_days)
    )

    return CreditLedgerEntry.objects.create(
        account=account,
        entry_type=CreditLedgerEntry.EntryType.CHARGE,
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=str(reference_id),
        idempotency_key=idempotency_key,
        due_date=due_date,
        created_by=created_by,
    )



@transaction.atomic
def record_credit_payment(
    *,
    account_id,
    amount,
    description,
    idempotency_key,
    received_by,
    reference_type='',
    reference_id='',
):
    """
    Record a customer repayment and allocate it to the oldest
    outstanding charges first.
    """

    # Validate payment amount.
    try:
        amount = Decimal(str(amount))
    except Exception:
        raise CreditLedgerError('Invalid payment amount.')

    if not amount.is_finite() or amount <= Decimal('0.00'):
        raise CreditLedgerError('Payment amount must be greater than zero.')

    if amount.quantize(Decimal('0.01')) != amount:
        raise CreditLedgerError(
            'Payment amount cannot have more than two decimal places.'
        )

    if not idempotency_key or len(idempotency_key) > 100:
        raise CreditLedgerError('A valid idempotency key is required.')

    # Lock the account to prevent conflicting transactions.
    try:
        account = CreditAccount.objects.select_for_update().get(
            pk=account_id
        )
    except CreditAccount.DoesNotExist:
        raise CreditLedgerError('Credit account does not exist.')

    # Make repeated requests safe.
    existing = CreditLedgerEntry.objects.filter(
        idempotency_key=idempotency_key
    ).first()

    if existing:
        if (
            existing.account_id == account.id
            and existing.entry_type == CreditLedgerEntry.EntryType.PAYMENT
            and existing.amount == amount
        ):
            return existing

        raise CreditLedgerError(
            'This idempotency key has already been used.'
        )

    # Suspended accounts can receive repayments.
    if account.status not in (
        CreditAccount.Status.ACTIVE,
        CreditAccount.Status.SUSPENDED,
    ):
        raise CreditLedgerError(
            'This account cannot receive payments in its current status.'
        )

    outstanding = account.outstanding_balance

    if outstanding <= Decimal('0.00'):
        raise CreditLedgerError(
            'This account has no outstanding balance.'
        )

    if amount > outstanding:
        raise CreditLedgerError(
            'Payment cannot exceed the outstanding balance.'
        )

    # Create the payment ledger entry.
    payment = CreditLedgerEntry.objects.create(
        account=account,
        entry_type=CreditLedgerEntry.EntryType.PAYMENT,
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=str(reference_id),
        idempotency_key=idempotency_key,
        created_by=received_by,
    )

    # Allocate payment to oldest outstanding charges first.
    remaining = amount

    charges = CreditLedgerEntry.objects.filter(
        account=account,
        entry_type=CreditLedgerEntry.EntryType.CHARGE,
    ).order_by('due_date', 'created_at', 'id')

    for charge in charges:
        if remaining <= Decimal('0.00'):
            break

        already_allocated = (
            charge.charge_allocations.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        )

        charge_balance = charge.amount - already_allocated

        if charge_balance <= Decimal('0.00'):
            continue

        allocation_amount = min(remaining, charge_balance)

        CreditPaymentAllocation.objects.create(
            payment_entry=payment,
            charge_entry=charge,
            amount=allocation_amount,
            allocated_by=received_by,
        )

        remaining -= allocation_amount

    # Roll back everything if the payment could not be fully allocated.
    if remaining > Decimal('0.00'):
        raise CreditLedgerError(
            'Payment allocation failed. No transaction was recorded.'
        )

    return payment
