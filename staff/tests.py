
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from branches.models import Branch
from .models import StaffProfile, ShiftAssignment
from .services import assign_staff_shift


User = get_user_model()


class StaffManagementTests(APITestCase):

    def setUp(self):
        self.client = APIClient()

        self.branch = Branch.objects.create(
            name='Kikuyu Branch',
            code='KIK-001',
            town='Kikuyu',
        )

        self.admin = User.objects.create_user(
            username='staff_admin',
            email='staffadmin@example.com',
            password='Admin-Password-2026!',
            role=User.Role.ADMIN,
        )

        self.owner = User.objects.create_user(
            username='staff_owner',
            email='staffowner@example.com',
            password='Owner-Password-2026!',
            role=User.Role.OWNER,
        )

        self.supervisor = User.objects.create_user(
            username='staff_supervisor',
            email='supervisor@example.com',
            password='Supervisor-Password-2026!',
            role=User.Role.SUPERVISOR,
        )

        self.cleaner = User.objects.create_user(
            username='staff_cleaner',
            email='cleaner@example.com',
            password='Cleaner-Password-2026!',
            role=User.Role.CLEANER,
        )

        self.staff = StaffProfile.objects.create(
            user=self.cleaner,
            staff_number='EMP-001',
            branch=self.branch,
            phone_number='0712345678',
            employment_status=StaffProfile.EmploymentStatus.ACTIVE,
            date_joined=timezone.localdate(),
        )

        self.list_url = reverse('staff_list_create')

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def registration_data(self, **overrides):
        data = {
            'username': 'new_cleaner',
            'email': 'newcleaner@example.com',
            'password': 'New-Cleaner-Password-2026!',
            'first_name': 'New',
            'last_name': 'Cleaner',
            'role': User.Role.CLEANER,
            'shift': ShiftAssignment.Shift.DAY,
            'staff_number': 'EMP-002',
            'branch': self.branch.pk,
            'phone_number': '0711111111',
            'date_joined': timezone.localdate().isoformat(),
        }

        data.update(overrides)
        return data

    def test_admin_can_register_staff(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        staff = StaffProfile.objects.get(
            staff_number='EMP-002'
        )

        user = User.objects.get(username='new_cleaner')

        self.assertEqual(user.role, User.Role.CLEANER)

        self.assertTrue(
            user.check_password('New-Cleaner-Password-2026!')
        )

        assignment = ShiftAssignment.objects.get(staff=staff)

        self.assertEqual(
            assignment.shift,
            ShiftAssignment.Shift.DAY
        )

        self.assertEqual(
            assignment.changed_by,
            self.admin
        )

        self.assertEqual(
            assignment.effective_from,
            timezone.localdate()
        )

    def test_owner_can_register_staff(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            self.registration_data(),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        staff = StaffProfile.objects.get(
            staff_number='EMP-002'
        )

        self.assertTrue(
            ShiftAssignment.objects.filter(
                staff=staff,
                shift=ShiftAssignment.Shift.DAY,
                changed_by=self.owner,
            ).exists()
        )

    def test_registration_requires_initial_shift(self):
        self.authenticate(self.admin)

        data = self.registration_data()
        data.pop('shift')

        response = self.client.post(
            self.list_url,
            data,
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            User.objects.filter(username='new_cleaner').exists()
        )

    def test_registration_accepts_night_shift(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                shift=ShiftAssignment.Shift.NIGHT,
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        staff = StaffProfile.objects.get(
            staff_number='EMP-002'
        )

        assignment = ShiftAssignment.objects.get(staff=staff)

        self.assertEqual(
            assignment.shift,
            ShiftAssignment.Shift.NIGHT
        )

    def test_admin_cannot_register_owner(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                role=User.Role.OWNER,
                username='unauthorized_owner',
                email='unauthorizedowner@example.com',
                staff_number='EMP-003',
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            User.objects.filter(
                username='unauthorized_owner'
            ).exists()
        )

    def test_admin_cannot_register_another_admin_as_staff(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                role=User.Role.ADMIN,
                username='new_admin',
                email='newadmin@example.com',
                staff_number='EMP-004',
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertFalse(
            User.objects.filter(username='new_admin').exists()
        )

    def test_supervisor_cannot_register_staff(self):
        self.authenticate(self.supervisor)

        response = self.client.post(
            self.list_url,
            self.registration_data(),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_cleaner_cannot_view_staff_list(self):
        self.authenticate(self.cleaner)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_admin_can_view_staff_list(self):
        self.authenticate(self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_owner_can_view_staff_list(self):
        self.authenticate(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_duplicate_staff_number_is_rejected(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                staff_number='EMP-001'
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_duplicate_username_is_rejected(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                username='staff_cleaner'
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_duplicate_email_is_rejected(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            self.registration_data(
                email='cleaner@example.com'
            ),
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_admin_can_update_staff_employment_status(self):
        self.authenticate(self.admin)

        url = reverse(
            'staff_detail',
            kwargs={'pk': self.staff.pk}
        )

        response = self.client.patch(
            url,
            {
                'employment_status': (
                    StaffProfile.EmploymentStatus.INACTIVE
                )
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.staff.refresh_from_db()

        self.assertEqual(
            self.staff.employment_status,
            StaffProfile.EmploymentStatus.INACTIVE
        )

    def test_staff_user_account_cannot_be_changed_through_profile(self):
        self.authenticate(self.admin)

        url = reverse(
            'staff_detail',
            kwargs={'pk': self.staff.pk}
        )

        response = self.client.patch(
            url,
            {'user': self.supervisor.pk},
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.staff.refresh_from_db()

        self.assertEqual(
            self.staff.user,
            self.cleaner
        )


class StaffShiftAssignmentTests(APITestCase):

    def setUp(self):
        self.client = APIClient()

        self.branch = Branch.objects.create(
            name='Kikuyu Branch',
            code='KIK-002',
            town='Kikuyu',
        )

        self.admin = User.objects.create_user(
            username='shift_admin',
            email='shiftadmin@example.com',
            password='Shift-Admin-Password-2026!',
            role=User.Role.ADMIN,
        )

        self.owner = User.objects.create_user(
            username='shift_owner',
            email='shiftowner@example.com',
            password='Shift-Owner-Password-2026!',
            role=User.Role.OWNER,
        )

        self.cleaner = User.objects.create_user(
            username='shift_cleaner',
            email='shiftcleaner@example.com',
            password='Shift-Cleaner-Password-2026!',
            role=User.Role.CLEANER,
        )

        self.staff = StaffProfile.objects.create(
            user=self.cleaner,
            staff_number='SHIFT-001',
            branch=self.branch,
            date_joined=timezone.localdate(),
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_service_creates_shift_assignment(self):
        assignment = assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.DAY,
            effective_from=timezone.localdate(),
            changed_by=self.admin,
        )

        self.assertEqual(
            assignment.shift,
            ShiftAssignment.Shift.DAY
        )

    def test_new_assignment_closes_previous_assignment(self):
        start_date = timezone.localdate()

        first = assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.DAY,
            effective_from=start_date,
            changed_by=self.admin,
        )

        second_date = start_date + timedelta(days=10)

        second = assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.NIGHT,
            effective_from=second_date,
            changed_by=self.admin,
        )

        first.refresh_from_db()

        self.assertEqual(
            first.effective_to,
            second_date - timedelta(days=1)
        )

        self.assertIsNone(second.effective_to)

    def test_backdated_shift_is_rejected_by_service(self):
        yesterday = timezone.localdate() - timedelta(days=1)

        with self.assertRaises(ValidationError):
            assign_staff_shift(
                staff_id=self.staff.pk,
                shift=ShiftAssignment.Shift.DAY,
                effective_from=yesterday,
                changed_by=self.admin,
            )

    def test_invalid_shift_is_rejected(self):
        with self.assertRaises(ValidationError):
            assign_staff_shift(
                staff_id=self.staff.pk,
                shift='EVENING',
                effective_from=timezone.localdate(),
                changed_by=self.admin,
            )

    def test_inactive_staff_cannot_receive_shift(self):
        self.staff.employment_status = (
            StaffProfile.EmploymentStatus.INACTIVE
        )
        self.staff.save()

        with self.assertRaises(ValidationError):
            assign_staff_shift(
                staff_id=self.staff.pk,
                shift=ShiftAssignment.Shift.DAY,
                effective_from=timezone.localdate(),
                changed_by=self.admin,
            )

    def test_suspended_staff_cannot_receive_shift(self):
        self.staff.employment_status = (
            StaffProfile.EmploymentStatus.SUSPENDED
        )
        self.staff.save()

        with self.assertRaises(ValidationError):
            assign_staff_shift(
                staff_id=self.staff.pk,
                shift=ShiftAssignment.Shift.DAY,
                effective_from=timezone.localdate(),
                changed_by=self.admin,
            )

    def test_future_assignments_preserve_previous_history(self):
        today = timezone.localdate()

        first = assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.DAY,
            effective_from=today,
            changed_by=self.admin,
        )

        future_date = today + timedelta(days=15)

        second = assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.NIGHT,
            effective_from=future_date,
            changed_by=self.admin,
        )

        first.refresh_from_db()

        self.assertEqual(
            first.effective_to,
            future_date - timedelta(days=1)
        )

        self.assertEqual(
            second.effective_from,
            future_date
        )

    def test_admin_can_change_staff_shift_through_api(self):
        self.authenticate(self.admin)

        url = reverse(
            'staff_shift_change',
            kwargs={'staff_id': self.staff.pk}
        )

        response = self.client.post(
            url,
            {
                'shift': ShiftAssignment.Shift.DAY,
                'effective_from': timezone.localdate().isoformat(),
                'reason': 'Initial assignment',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_owner_can_change_staff_shift_through_api(self):
        self.authenticate(self.owner)

        url = reverse(
            'staff_shift_change',
            kwargs={'staff_id': self.staff.pk}
        )

        response = self.client.post(
            url,
            {
                'shift': ShiftAssignment.Shift.NIGHT,
                'effective_from': timezone.localdate().isoformat(),
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_shift_history_is_available_to_admin(self):
        self.authenticate(self.admin)

        assign_staff_shift(
            staff_id=self.staff.pk,
            shift=ShiftAssignment.Shift.DAY,
            effective_from=timezone.localdate(),
            changed_by=self.admin,
        )

        url = reverse(
            'staff_shift_history',
            kwargs={'staff_id': self.staff.pk}
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(response.data), 1)
