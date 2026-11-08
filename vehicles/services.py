
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.db import connection
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)


class CreditLedgerError(Exception):
    """Raised when a credit ledger operation violates business rules."""


ZERO = Decimal("0.00")
MAX_MONEY_AMOUNT = Decimal("9999999999.99")

def lock_idempotency_key(key):
    """
    Serialize transactions using the same idempotency key.

    PostgreSQL releases this transaction-level lock automatically
    when the surrounding transaction commits or rolls back.
    """
    if connection.vendor != "postgresql":
        raise CreditLedgerError(
            "Idempotency locking requires PostgreSQL."
        )

    # PostgreSQL advisory locks accept two signed 32-bit integers.
    # Hash the key to produce a stable lock identifier.
    import hashlib

    digest = hashlib.blake2b(
        key.encode("utf-8"),
        digest_size=8,
    ).digest()

    first = int.from_bytes(
        digest[:4], byteorder="big", signed=True
    )
    second = int.from_bytes(
        digest[4:], byteorder="big", signed=True
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [first, second],
        )



from decimal import Decimal, InvalidOperation


def validate_money_amount(amount):
    """
    Validate and normalize a monetary amount.
    Always return a Decimal.
    """

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise CreditLedgerError("Invalid monetary amount.")

    if not amount.is_finite():
        raise CreditLedgerError("Amount must be a finite number.")

    if amount <= Decimal("0.00"):
        raise CreditLedgerError("Amount must be greater than zero.")

    if amount > MAX_MONEY_AMOUNT:
        raise CreditLedgerError("Amount exceeds the maximum permitted value.")

    if amount.as_tuple().exponent < -2:
        raise CreditLedgerError(
            "Amount cannot have more than two decimal places."
        )

    return amount



def validate_idempotency_key(idempotency_key):
    """Validate an idempotency key before creating a ledger entry."""
    key = str(idempotency_key or "").strip()

    if not key:
        raise CreditLedgerError("An idempotency key is required.")

    if len(key) > 100:
        raise CreditLedgerError(
            "The idempotency key cannot exceed 100 characters."
        )

    return key


def validate_transaction_details(
    existing,
    account,
    entry_type,
    amount,
    description,
    reference_type,
    reference_id,
):
    """Check whether an existing transaction is an exact retry."""
    return (
        existing.account_id == account.id
        and existing.entry_type == entry_type
        and existing.amount == amount
        and existing.description == description
        and existing.reference_type == reference_type
        and existing.reference_id == str(reference_id or "")
    )


def get_locked_credit_account(account_id):
    """
    Retrieve and lock a credit account.

    All financial operations on an account should acquire this lock
    before reading or changing its ledger.
    """
    account = (
        CreditAccount.objects
        .select_for_update()
        .select_related("customer")
        .filter(pk=account_id)
        .first()
    )

    if account is None:
        raise CreditLedgerError("Credit account not found.")

    return account


def get_existing_transaction(idempotency_key):
    """Find an existing transaction using its unique idempotency key."""
    return CreditLedgerEntry.objects.filter(
        idempotency_key=idempotency_key
    ).first()


def calculate_charge_allocated_amount(charge):
    """Calculate the amount already allocated against a charge."""
    return (
        CreditPaymentAllocation.objects
        .filter(charge_entry=charge)
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )


@transaction.atomic
def create_credit_charge(
    account_id,
    amount,
    description,
    idempotency_key,
    created_by,
    reference_type="",
    reference_id="",
):
    """
    Record a new charge against a customer's credit account.

    The account must be active and have sufficient available credit.

    Repeated requests with identical transaction details return
    the existing charge instead of creating a duplicate.
    """
    amount = validate_money_amount(amount)
    idempotency_key = validate_idempotency_key(idempotency_key)
    lock_idempotency_key(idempotency_key)

    description = str(description or "").strip()
    reference_type = str(reference_type or "").strip()
    reference_id = str(reference_id or "")

    if not description:
        raise CreditLedgerError("A charge description is required.")

    account = get_locked_credit_account(account_id)

    existing = get_existing_transaction(idempotency_key)

    if existing:
        if validate_transaction_details(
            existing=existing,
            account=account,
            entry_type=CreditLedgerEntry.EntryType.CHARGE,
            amount=amount,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
        ):
            return existing

        raise CreditLedgerError(
            "This idempotency key has already been used "
            "with different transaction details."
        )

    if account.status != CreditAccount.Status.ACTIVE:
        raise CreditLedgerError(
            "Only active credit accounts can receive new charges."
        )

    if not account.customer.is_active:
        raise CreditLedgerError(
            "This customer account is inactive."
        )

    outstanding = account.outstanding_balance

    if outstanding < ZERO:
        raise CreditLedgerError(
            "The credit account has an invalid negative balance."
        )

    if account.credit_limit is not None:
        if outstanding + amount > account.credit_limit:
            raise CreditLedgerError(
                "This charge would exceed the customer's credit limit."
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
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        due_date=due_date,
        created_by=created_by,
    )


@transaction.atomic
def record_credit_payment(
    account_id,
    amount,
    description,
    idempotency_key,
    received_by,
    reference_type="",
    reference_id="",
):
    """
    Record a repayment against a customer's credit account.

    Payments are allocated automatically to the oldest outstanding
    charges first.

    Suspended accounts may receive repayments, but pending and closed
    accounts cannot.

    The payment and all its allocations are committed together.
    If allocation fails, the entire transaction is rolled back.
    """
    amount = validate_money_amount(amount)
    idempotency_key = validate_idempotency_key(idempotency_key)
    lock_idempotency_key(idempotency_key)

    description = str(description or "").strip()
    reference_type = str(reference_type or "").strip()
    reference_id = str(reference_id or "")

    if not description:
        raise CreditLedgerError("A payment description is required.")

    # Lock the account before checking its balance or allocating money.
    account = get_locked_credit_account(account_id)

    # Idempotency check happens before balance validation.
    existing = get_existing_transaction(idempotency_key)

    if existing:
        if validate_transaction_details(
            existing=existing,
            account=account,
            entry_type=CreditLedgerEntry.EntryType.PAYMENT,
            amount=amount,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
        ):
            return existing

        raise CreditLedgerError(
            "This idempotency key has already been used "
            "with different transaction details."
        )

    if account.status not in (
        CreditAccount.Status.ACTIVE,
        CreditAccount.Status.SUSPENDED,
    ):
        raise CreditLedgerError(
            "This account cannot receive repayments."
        )

    # Calculate the current ledger balance after acquiring the lock.
    outstanding = account.outstanding_balance

    if outstanding <= ZERO:
        raise CreditLedgerError(
            "This credit account has no outstanding balance."
        )

    if amount > outstanding:
        raise CreditLedgerError(
            "The payment cannot exceed the outstanding balance."
        )

    # Create the payment inside the same atomic transaction.
    payment = CreditLedgerEntry.objects.create(
        account=account,
        entry_type=CreditLedgerEntry.EntryType.PAYMENT,
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        due_date=None,
        created_by=received_by,
    )

    remaining = amount

    # Lock charge rows in a consistent order before allocating.
    outstanding_charges = list(
        CreditLedgerEntry.objects
        .select_for_update()
        .filter(
            account=account,
            entry_type=CreditLedgerEntry.EntryType.CHARGE,
        )
        .order_by("due_date", "created_at", "id")
    )

    for charge in outstanding_charges:
        if remaining <= ZERO:
            break

        # Recalculate allocations from current database records.
        allocated = calculate_charge_allocated_amount(charge)

        charge_balance = charge.amount - allocated

        if charge_balance <= ZERO:
            continue

        allocation_amount = min(
            remaining,
            charge_balance,
        )

        CreditPaymentAllocation.objects.create(
            payment_entry=payment,
            charge_entry=charge,
            amount=allocation_amount,
            allocated_by=received_by,
        )

        remaining -= allocation_amount

    # Never commit a payment that has not been fully allocated.
    if remaining != ZERO:
        raise CreditLedgerError(
            "The payment could not be fully allocated. "
            "The transaction has been cancelled."
        )

    # Final verification: all payment value must have allocations.
    total_allocated = (
        CreditPaymentAllocation.objects
        .filter(payment_entry=payment)
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    if total_allocated != payment.amount:
        raise CreditLedgerError(
            "Payment allocation verification failed. "
            "The transaction has been cancelled."
        )

    return payment
