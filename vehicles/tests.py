
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

from branches.models import Branch

from .models import (
    Customer,
    Vehicle,
    VehicleCategory,
    CreditAccount,
    CreditLedgerEntry,
    CreditPaymentAllocation,
)

from .serializers import VehicleSerializer

from .services import (
    CreditLedgerError,
    create_credit_charge,
    record_credit_payment,
)


User = get_user_model()


class CreditLedgerServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='ledger_admin',
            password='TestPassword123!',
            email='ledger@example.com',
        )

        self.branch = Branch.objects.create(
            name='Test Branch',
            code='TEST01',
            town='Kikuyu',
        )

        self.customer = Customer.objects.create(
            full_name='Test Customer',
            phone_number='0712345678',
        )

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
        first = self.create_charge('250.00', 'charge-011')

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
        self.create_charge('500.00', 'charge-012')

        first = self.record_payment('200.00', 'payment-007')

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

        self.assertEqual(
            CreditLedgerEntry.objects.filter(
                idempotency_key='payment-007'
            ).count(),
            1,
        )

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


class VehicleCategoryAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            username='category_admin',
            email='categoryadmin@example.com',
            password='TestPassword123!',
            role='ADMIN',
        )

        self.supervisor = User.objects.create_user(
            username='category_supervisor',
            email='categorysupervisor@example.com',
            password='TestPassword123!',
            role='SUPERVISOR',
        )

        self.owner = User.objects.create_user(
            username='category_owner',
            email='categoryowner@example.com',
            password='TestPassword123!',
            role='OWNER',
        )

        self.cleaner = User.objects.create_user(
            username='category_cleaner',
            email='categorycleaner@example.com',
            password='TestPassword123!',
            role='CLEANER',
        )

        self.detailer = User.objects.create_user(
            username='category_detailer',
            email='categorydetailer@example.com',
            password='TestPassword123!',
            role='DETAILER',
        )

        self.category_url = '/api/vehicles/categories/'

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_authenticated_user_can_list_active_categories(self):
        active_category = VehicleCategory.objects.create(
            name='SUV',
            is_active=True,
        )

        VehicleCategory.objects.create(
            name='Inactive Category',
            is_active=False,
        )

        self.authenticate(self.cleaner)

        response = self.client.get(self.category_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], active_category.id)
        self.assertEqual(response.data[0]['name'], 'SUV')

    def test_admin_can_create_category(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.category_url,
            {'name': '  Luxury   SUV  '},
            format='json',
        )

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            VehicleCategory.objects.filter(
                name='Luxury SUV'
            ).exists()
        )

    def test_supervisor_can_create_category(self):
        self.authenticate(self.supervisor)

        response = self.client.post(
            self.category_url,
            {'name': 'Pickup'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            VehicleCategory.objects.filter(
                name='Pickup'
            ).exists()
        )

    def test_owner_cannot_create_category(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.category_url,
            {'name': 'Owner Created Category'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            VehicleCategory.objects.filter(
                name='Owner Created Category'
            ).exists()
        )

    def test_cleaner_cannot_create_category(self):
        self.authenticate(self.cleaner)

        response = self.client.post(
            self.category_url,
            {'name': 'Cleaner Created Category'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            VehicleCategory.objects.filter(
                name='Cleaner Created Category'
            ).exists()
        )

    def test_detailer_cannot_create_category(self):
        self.authenticate(self.detailer)

        response = self.client.post(
            self.category_url,
            {'name': 'Detailer Created Category'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            VehicleCategory.objects.filter(
                name='Detailer Created Category'
            ).exists()
        )

    def test_duplicate_category_name_is_rejected(self):
        VehicleCategory.objects.create(name='SUV')

        self.authenticate(self.admin)

        response = self.client.post(
            self.category_url,
            {'name': 'SUV'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            VehicleCategory.objects.filter(name='SUV').count(),
            1,
        )

    def test_blank_category_name_is_rejected(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.category_url,
            {'name': '   '},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(VehicleCategory.objects.count(), 0)


class VehicleRegistrationNormalizationTests(TestCase):

    def setUp(self):
        self.branch = Branch.objects.create(
            name='Registration Test Branch',
            code='REGTEST01',
            town='Kikuyu',
        )

        self.category = VehicleCategory.objects.create(
            name='SUV',
            is_active=True,
        )

    def create_vehicle(self, registration_number):
        return Vehicle.objects.create(
            registration_number=registration_number,
            make_model='Toyota Harrier',
            category=self.category,
            vehicle_type=Vehicle.VehicleType.SUV,
            branch=self.branch,
        )

    def test_model_save_removes_spaces_and_uppercases_registration(self):
        vehicle = self.create_vehicle('kda 123a')

        vehicle.refresh_from_db()

        self.assertEqual(
            vehicle.registration_number,
            'KDA123A',
        )

    def test_model_save_removes_multiple_whitespace_characters(self):
        vehicle = self.create_vehicle('  kdb   456b  ')

        vehicle.refresh_from_db()

        self.assertEqual(
            vehicle.registration_number,
            'KDB456B',
        )

    def test_serializer_normalizes_registration_number(self):
        serializer = VehicleSerializer(data={
            'registration_number': 'kdc 789a',
            'make_model': 'Toyota Prado',
            'category': self.category.pk,
            'branch': self.branch.pk,
        })

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data['registration_number'],
            'KDC789A',
        )

        vehicle = serializer.save()

        vehicle.refresh_from_db()

        self.assertEqual(
            vehicle.registration_number,
            'KDC789A',
        )

    def test_serializer_rejects_duplicate_with_different_spacing_and_case(self):
        self.create_vehicle('KDA123A')

        serializer = VehicleSerializer(data={
            'registration_number': 'kda 123a',
            'make_model': 'Toyota Harrier',
            'category': self.category.pk,
            'branch': self.branch.pk,
        })

        self.assertFalse(serializer.is_valid())

        self.assertIn(
            'registration_number',
            serializer.errors,
        )

    def test_serializer_allows_unchanged_registration_on_update(self):
        vehicle = self.create_vehicle('KDA 123A')

        serializer = VehicleSerializer(
            instance=vehicle,
            data={
                'registration_number': 'kda 123a',
                'make_model': 'Toyota Harrier',
                'category': self.category.pk,
                'branch': self.branch.pk,
            },
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        updated_vehicle = serializer.save()

        self.assertEqual(
            updated_vehicle.registration_number,
            'KDA123A',
        )


class VehicleSearchAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='vehicle_search_user',
            email='vehiclesearch@example.com',
            password='TestPassword123!',
            role='CLEANER',
        )

        self.branch = Branch.objects.create(
            name='Vehicle Search Branch',
            code='VSEARCH01',
            town='Kikuyu',
        )

        self.category = VehicleCategory.objects.create(
            name='SUV',
            is_active=True,
        )

        self.vehicle = Vehicle.objects.create(
            registration_number='KDA 123A',
            make_model='Toyota Harrier',
            category=self.category,
            vehicle_type=Vehicle.VehicleType.SUV,
            branch=self.branch,
        )

        self.second_vehicle = Vehicle.objects.create(
            registration_number='KDB 456B',
            make_model='Nissan X-Trail',
            category=self.category,
            vehicle_type=Vehicle.VehicleType.SUV,
            branch=self.branch,
        )

        self.vehicle_url = '/api/vehicles/'

        self.client.force_authenticate(user=self.user)

    def test_search_finds_vehicle_by_registration_without_spaces(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'KDA123A'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['registration_number'],
            'KDA123A',
        )

    def test_search_finds_vehicle_by_registration_with_spaces(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'KDA 123A'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['registration_number'],
            'KDA123A',
        )

    def test_search_finds_vehicle_by_lowercase_registration_with_spaces(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'kda 123a'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['registration_number'],
            'KDA123A',
        )

    def test_search_finds_vehicle_by_partial_registration(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'KDA'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['id'],
            self.vehicle.id,
        )

    def test_search_finds_vehicle_by_make_model(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'Toyota'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['id'],
            self.vehicle.id,
        )

    def test_search_finds_vehicle_by_partial_model(self):
        response = self.client.get(
            self.vehicle_url,
            {'search': 'X-Trail'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['id'],
            self.second_vehicle.id,
        )

    def test_empty_search_returns_all_vehicles(self):
        response = self.client.get(self.vehicle_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
