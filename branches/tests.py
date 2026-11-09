
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Branch


User = get_user_model()


class BranchManagementTests(APITestCase):

    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            username='branch_owner',
            email='branchowner@example.com',
            password='Owner-Password-2026!',
            role=User.Role.OWNER,
        )

        self.admin = User.objects.create_user(
            username='branch_admin',
            email='branchadmin@example.com',
            password='Admin-Password-2026!',
            role=User.Role.ADMIN,
        )

        self.supervisor = User.objects.create_user(
            username='branch_supervisor',
            email='supervisor@example.com',
            password='Supervisor-Password-2026!',
            role=User.Role.SUPERVISOR,
        )

        self.accounts = User.objects.create_user(
            username='branch_accounts',
            email='accounts@example.com',
            password='Accounts-Password-2026!',
            role=User.Role.ACCOUNTS,
        )

        self.cleaner = User.objects.create_user(
            username='branch_cleaner',
            email='cleaner@example.com',
            password='Cleaner-Password-2026!',
            role=User.Role.CLEANER,
        )

        self.detailer = User.objects.create_user(
            username='branch_detailer',
            email='detailer@example.com',
            password='Detailer-Password-2026!',
            role=User.Role.DETAILER,
        )

        self.branch = Branch.objects.create(
            name='Kikuyu Branch',
            code='KIK-001',
            town='Kikuyu',
        )

        self.list_url = reverse('branch_list_create')
        self.detail_url = reverse(
            'branch_detail',
            kwargs={'pk': self.branch.pk}
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def branch_data(self, **overrides):
        data = {
            'name': 'Karen Branch',
            'code': 'KAR-001',
            'town': 'Karen',
            'address': 'Karen Road',
            'phone': '0712345678',
            'email': 'karen@example.com',
            'is_active': True,
        }
        data.update(overrides)
        return data

    def test_owner_can_list_branches(self):
        self.authenticate(self.owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_list_branches(self):
        self.authenticate(self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_create_branch(self):
        self.authenticate(self.owner)
        response = self.client.post(
            self.list_url,
            self.branch_data(),
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Branch.objects.filter(code='KAR-001').exists()
        )

    def test_admin_can_create_branch(self):
        self.authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            self.branch_data(),
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_can_update_branch(self):
        self.authenticate(self.owner)
        response = self.client.patch(
            self.detail_url,
            {'name': 'Updated Kikuyu Branch'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_update_branch(self):
        self.authenticate(self.admin)
        response = self.client.patch(
            self.detail_url,
            {'name': 'Updated Kikuyu Branch'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_roles_cannot_list_branches(self):
        for user in [
            self.supervisor,
            self.accounts,
            self.cleaner,
            self.detailer,
        ]:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.list_url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN
                )

    def test_non_admin_roles_cannot_create_branch(self):
        for user in [
            self.supervisor,
            self.accounts,
            self.cleaner,
            self.detailer,
        ]:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.post(
                    self.list_url,
                    self.branch_data(
                        code=f'{user.role}-001'
                    ),
                    format='json'
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN
                )

    def test_non_admin_roles_cannot_update_branch(self):
        for user in [
            self.supervisor,
            self.accounts,
            self.cleaner,
            self.detailer,
        ]:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.patch(
                    self.detail_url,
                    {'name': 'Unauthorized Update'},
                    format='json'
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN
                )

    def test_unauthenticated_user_cannot_list_branches(self):
        response = self.client.get(self.list_url)
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_duplicate_branch_code_is_rejected(self):
        self.authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            self.branch_data(
                code='KIK-001'
            ),
            format='json'
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_inactive_branch_can_be_reactivated(self):
        self.branch.is_active = False
        self.branch.save()

        self.authenticate(self.owner)
        response = self.client.patch(
            self.detail_url,
            {'is_active': True},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.branch.refresh_from_db()
        self.assertTrue(self.branch.is_active)
