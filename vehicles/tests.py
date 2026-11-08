
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

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

    def test_reject_amount_above_maximum(self):
        with self.assertRaises(CreditLedgerError):
            self.create_charge(
                '10000000000.00',
                'charge-too-large',
            )

        self.assertEqual(
            CreditLedgerEntry.objects.count(),
            0,
        )

    def test_reject_amount_with_more_than_two_decimal_places(self):
        with self.assertRaises(CreditLedgerError):
            self.create_charge(
                '100.999',
                'charge-invalid-precision',
            )

        self.assertEqual(
            CreditLedgerEntry.objects.count(),
            0,
        )

    def test_accept_amount_at_maximum_supported_value(self):
        self.account.credit_limit = None
        self.account.save(update_fields=['credit_limit'])

        charge = self.create_charge(
            '9999999999.99',
            'charge-maximum',
        )

        self.assertEqual(
            charge.amount,
            Decimal('9999999999.99'),
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

    
    def test_reject_duplicate_charge_key_with_different_details(self):
        # First transaction.
        first = self.create_charge('250.00', 'charge-011')

        # Reuse the same key but change the description.
        with self.assertRaises(CreditLedgerError):
            create_credit_charge(
                account_id=self.account.id,
                amount='250.00',
                description='Different carwash service',
                idempotency_key='charge-011',
                created_by=self.user,
                reference_type='TEST',
                reference_id='charge-011',
            )

        # Only the original charge should exist.
        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                idempotency_key='charge-011'
            ).count(),
            1,
        )

        self.assertEqual(
            first.amount,
            Decimal('250.00'),
        )

    def test_reject_duplicate_payment_key_with_different_details(self):
        # Create an outstanding charge first.
        self.create_charge('500.00', 'charge-012')

        # First repayment.
        first = self.record_payment('200.00', 'payment-007')

        # Reuse the same key but change the description.
        with self.assertRaises(CreditLedgerError):
            record_credit_payment(
                account_id=self.account.id,
                amount='200.00',
                description='Different repayment description',
                idempotency_key='payment-007',
                received_by=self.user,
                reference_type='TEST',
                reference_id='payment-007',
            )

        # Only the original repayment should exist.
        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                idempotency_key='payment-007'
            ).count(),
            1,
        )

        # The original allocation must remain unchanged.
        self.assertEqual(
            CreditPaymentAllocation.objects.filter(
                payment_entry=first
            ).count(),
            1,
        )

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('300.00'),
        )


class CreditLedgerAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.branch = Branch.objects.create(
            name='API Test Branch',
            code='API01',
            town='Kikuyu',
        )

        self.customer = Customer.objects.create(
            full_name='API Test Customer',
            phone_number='0712345679',
        )

        self.admin = User.objects.create_user(
            username='api_admin',
            email='apiadmin@example.com',
            password='TestPassword123!',
            role='ADMIN',
        )

        self.accounts_user = User.objects.create_user(
            username='api_accounts',
            email='accounts@example.com',
            password='TestPassword123!',
            role='ACCOUNTS',
        )

        self.owner = User.objects.create_user(
            username='api_owner',
            email='owner@example.com',
            password='TestPassword123!',
            role='OWNER',
        )

        self.supervisor = User.objects.create_user(
            username='api_supervisor',
            email='supervisor@example.com',
            password='TestPassword123!',
            role='SUPERVISOR',
        )

        self.cleaner = User.objects.create_user(
            username='api_cleaner',
            email='cleaner@example.com',
            password='TestPassword123!',
            role='CLEANER',
        )

        self.account = CreditAccount.objects.create(
            customer=self.customer,
            account_number='CR-API-001',
            credit_limit=Decimal('2000.00'),
            payment_terms_days=30,
            status=CreditAccount.Status.ACTIVE,
            approved_by=self.admin,
        )

        self.base_url = (
            f'/api/vehicles/credit-accounts/{self.account.pk}/'
        )

    def create_charge(self, amount='500.00'):
        return create_credit_charge(
            account_id=self.account.id,
            amount=amount,
            description='API test carwash service',
            idempotency_key='api-charge-001',
            created_by=self.admin,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_admin_can_record_repayment(self):
        self.create_charge()
        self.authenticate(self.admin)

        response = self.client.post(
            self.base_url + 'payments/',
            {
                'amount': '200.00',
                'description': 'Cash repayment',
                'idempotency_key': 'api-payment-001',
                'reference_type': 'CASH',
                'reference_id': 'RECEIPT-001',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                entry_type=CreditLedgerEntry.EntryType.PAYMENT
            ).count(),
            1,
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('300.00'),
        )

    def test_accounts_user_can_record_repayment(self):
        self.create_charge()
        self.authenticate(self.accounts_user)

        response = self.client.post(
            self.base_url + 'payments/',
            {
                'amount': '100.00',
                'description': 'Accounts repayment',
                'idempotency_key': 'api-payment-002',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)

    def test_owner_can_view_ledger(self):
        self.create_charge()
        self.authenticate(self.owner)

        response = self.client.get(self.base_url + 'ledger/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_owner_cannot_record_repayment(self):
        self.create_charge()
        self.authenticate(self.owner)

        response = self.client.post(
            self.base_url + 'payments/',
            {
                'amount': '100.00',
                'description': 'Owner repayment attempt',
                'idempotency_key': 'api-payment-003',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_supervisor_cannot_view_ledger(self):
        self.authenticate(self.supervisor)

        response = self.client.get(self.base_url + 'ledger/')

        self.assertEqual(response.status_code, 403)

    def test_cleaner_cannot_record_repayment(self):
        self.create_charge()
        self.authenticate(self.cleaner)

        response = self.client.post(
            self.base_url + 'payments/',
            {
                'amount': '100.00',
                'description': 'Cleaner repayment attempt',
                'idempotency_key': 'api-payment-004',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_ledger_shows_charge_and_repayment(self):
        self.create_charge()

        record_credit_payment(
            account_id=self.account.id,
            amount='200.00',
            description='Test repayment',
            idempotency_key='api-payment-005',
            received_by=self.admin,
        )

        self.authenticate(self.accounts_user)

        response = self.client.get(self.base_url + 'ledger/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_allocations_endpoint_returns_payment_allocation(self):
        self.create_charge()

        record_credit_payment(
            account_id=self.account.id,
            amount='200.00',
            description='Test repayment',
            idempotency_key='api-payment-006',
            received_by=self.admin,
        )

        self.authenticate(self.accounts_user)

        response = self.client.get(
            self.base_url + 'allocations/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_invalid_repayment_does_not_change_balance(self):
        self.create_charge()
        self.authenticate(self.admin)

        response = self.client.post(
            self.base_url + 'payments/',
            {
                'amount': '900.00',
                'description': 'Excess repayment',
                'idempotency_key': 'api-payment-007',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.outstanding_balance,
            Decimal('500.00'),
        )
