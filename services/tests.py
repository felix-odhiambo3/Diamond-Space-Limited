
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from services.models import Service


class ServiceAPITests(TestCase):
    
    def test_negative_service_price_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/services/', {
            'name': 'Invalid Wash',
            'code': 'NEG001',
            'category': 'CAR_WASH',
            'price': '-100.00',
        })

        self.assertEqual(response.status_code, 400)

    def test_zero_service_price_is_allowed(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/services/', {
            'name': 'Complimentary Wash',
            'code': 'FREE001',
            'category': 'CAR_WASH',
            'price': '0.00',
        })

        self.assertEqual(response.status_code, 201)

    def test_zero_service_duration_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/services/', {
            'name': 'Invalid Duration Wash',
            'code': 'DUR001',
            'category': 'CAR_WASH',
            'price': '500.00',
            'duration_minutes': 0,
        })

        self.assertEqual(response.status_code, 400)

    def test_detailing_service_does_not_require_timer(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/services/', {
            'name': 'Full Detailing',
            'code': 'DET001',
            'category': 'DETAILING',
            'price': '2500.00',
            'duration_minutes': 120,
            'requires_timer': True,
        })

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['requires_timer'])


    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='TestPass123!',
            role='OWNER',
        )

        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='TestPass123!',
            role='ADMIN',
        )

        self.supervisor = User.objects.create_user(
            username='supervisor',
            email='supervisor@example.com',
            password='TestPass123!',
            role='SUPERVISOR',
        )

        self.cleaner = User.objects.create_user(
            username='cleaner',
            email='cleaner@example.com',
            password='TestPass123!',
            role='CLEANER',
        )

        self.active_service = Service.objects.create(
            name='Basic Wash',
            code='BASIC001',
            category='CAR_WASH',
            price=Decimal('500.00'),
            duration_minutes=30,
            is_active=True,
        )

        self.inactive_service = Service.objects.create(
            name='Old Wash',
            code='OLD001',
            category='CAR_WASH',
            price=Decimal('400.00'),
            duration_minutes=25,
            is_active=False,
        )

    def test_owner_can_create_service(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post('/api/services/', {
            'name': 'Premium Wash',
            'code': 'PREM001',
            'category': 'CAR_WASH',
            'price': '1000.00',
            'duration_minutes': 45,
            'requires_timer': True,
        })

        self.assertEqual(response.status_code, 201)

    def test_admin_can_create_service(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/services/', {
            'name': 'Interior Cleaning',
            'code': 'INT001',
            'category': 'DETAILING',
            'price': '1500.00',
        })

        self.assertEqual(response.status_code, 201)

    def test_supervisor_cannot_create_service(self):
        self.client.force_authenticate(user=self.supervisor)

        response = self.client.post('/api/services/', {
            'name': 'New Wash',
            'code': 'NEW001',
            'category': 'CAR_WASH',
            'price': '600.00',
        })

        self.assertEqual(response.status_code, 403)

    def test_cleaner_can_view_active_services(self):
        self.client.force_authenticate(user=self.cleaner)

        response = self.client.get('/api/services/')

        self.assertEqual(response.status_code, 200)

        returned_ids = [
            item['id'] for item in response.data
        ]

        self.assertIn(self.active_service.id, returned_ids)
        self.assertNotIn(self.inactive_service.id, returned_ids)

    def test_owner_can_view_inactive_services(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get('/api/services/')

        self.assertEqual(response.status_code, 200)

        returned_ids = [
            item['id'] for item in response.data
        ]

        self.assertIn(self.inactive_service.id, returned_ids)

    def test_admin_can_update_service(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/services/{self.active_service.id}/',
            {'price': '750.00'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)

        self.active_service.refresh_from_db()

        self.assertEqual(
            self.active_service.price,
            Decimal('750.00'),
        )

    def test_cleaner_cannot_update_service(self):
        self.client.force_authenticate(user=self.cleaner)

        response = self.client.patch(
            f'/api/services/{self.active_service.id}/',
            {'price': '750.00'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_inactive_service(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            f'/api/services/{self.inactive_service.id}/',
            {'is_active': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)

        self.inactive_service.refresh_from_db()

        self.assertTrue(self.inactive_service.is_active)

    def test_unauthenticated_user_cannot_view_services(self):
        response = self.client.get('/api/services/')

        self.assertEqual(response.status_code, 401)
