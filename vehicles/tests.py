
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase

from branches.models import Branch
from .models import (
    Customer,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)
from .services import (
    CreditLedgerError,
    create_credit_charge,
    record_credit_payment,
)


User = get_user_model()


class CreditLedgerServiceTests(TestCase):

    def setUp(self):
        # Create a test administrator.
        self.user = User.objects.create_user(
            username='ledger_admin',
            password='TestPassword123!',
            email='ledger@example.com',
        )

        # Create a test branch.
        self.branch = Branch.objects.create(
            name='Test Branch',
            code='TEST01',
            town='Kikuyu',
        )

        # Create a test customer.
        self.customer = Customer.objects.create(
            full_name='Test Customer',
            phone_number='0712345678',
        )

        # Create an active credit account.
        self.account = CreditAccount.objects.create(
            customer=self.customer,
            account_number='CR-TEST-001',
            credit_limit=Decimal('1000.00'),
            payment_terms_days=30,
            status=CreditAccount.Status.ACTIVE,
            approved_by=self.user,
        )

    def create_charge(self, amount, key):
        return create_credit_charge(
            account_id=self.account.id,
            amount=amount,
            description='Test carwash service',
            idempotency_key=key,
            created_by=self.user,
            reference_type='TEST',
            reference_id=key,
        )

    def record_payment(self, amount, key):
        return record_credit_payment(
            account_id=self.account.id,
            amount=amount,
            description='Test customer repayment',
            idempotency_key=key,
            received_by=self.user,
            reference_type='TEST',
            reference_id=key,
        )

    def test_create_credit_charge(self):
        charge = self.create_charge('300.00', 'charge-001')

        self.assertEqual(
            charge.entry_type,
            CreditLedgerEntry.EntryType.CHARGE,
        )
        self.assertEqual(charge.amount, Decimal('300.00'))
        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('300.00'),
        )

    def test_reject_charge_exceeding_credit_limit(self):
        with self.assertRaises(CreditLedgerError):
            self.create_charge('1100.00', 'charge-002')

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('0.00'),
        )

    def test_record_partial_payment(self):
        self.create_charge('500.00', 'charge-003')

        payment = self.record_payment('200.00', 'payment-001')

        self.assertEqual(
            payment.entry_type,
            CreditLedgerEntry.EntryType.PAYMENT,
        )
        self.assertEqual(payment.amount, Decimal('200.00'))

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('300.00'),
        )

        allocation = CreditPaymentAllocation.objects.get(
            payment_entry=payment
        )

        self.assertEqual(
            allocation.amount,
            Decimal('200.00'),
        )

    def test_allocate_payment_across_multiple_charges(self):
        self.create_charge('100.00', 'charge-004')
        self.create_charge('200.00', 'charge-005')

        payment = self.record_payment('150.00', 'payment-002')

        allocations = CreditPaymentAllocation.objects.filter(
            payment_entry=payment
        ).order_by('charge_entry__created_at', 'charge_entry_id')

        self.assertEqual(allocations.count(), 2)

        self.assertEqual(
            allocations.aggregate(total=Sum('amount'))['total'],
            Decimal('150.00'),
        )

        self.assertEqual(
            allocations.first().amount,
            Decimal('100.00'),
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('150.00'),
        )

    def test_reject_payment_above_outstanding_balance(self):
        self.create_charge('300.00', 'charge-006')

        with self.assertRaises(CreditLedgerError):
            self.record_payment('400.00', 'payment-003')

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('300.00'),
        )

    def test_prevent_duplicate_charge(self):
        first = self.create_charge('250.00', 'charge-007')
        second = self.create_charge('250.00', 'charge-007')

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                idempotency_key='charge-007'
            ).count(),
            1,
        )

    def test_prevent_duplicate_payment(self):
        self.create_charge('500.00', 'charge-008')

        first = self.record_payment('200.00', 'payment-004')
        second = self.record_payment('200.00', 'payment-004')

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                idempotency_key='payment-004'
            ).count(),
            1,
        )

        self.assertEqual(
            CreditPaymentAllocation.objects.filter(
                payment_entry=first
            ).count(),
            1,
        )

    def test_suspended_account_can_receive_repayment(self):
        self.create_charge('300.00', 'charge-009')

        self.account.status = CreditAccount.Status.SUSPENDED
        self.account.save(update_fields=['status'])

        payment = self.record_payment('100.00', 'payment-005')

        self.assertEqual(
            payment.amount,
            Decimal('100.00'),
        )

    def test_closed_account_cannot_receive_payment(self):
        self.create_charge('300.00', 'charge-010')

        self.account.status = CreditAccount.Status.CLOSED
        self.account.save(update_fields=['status'])

        with self.assertRaises(CreditLedgerError):
            self.record_payment('100.00', 'payment-006')
