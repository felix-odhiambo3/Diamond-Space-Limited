
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from branches.models import Branch
from vehicles.models import Vehicle
from services.models import Service
from staff.models import StaffProfile
from .models import Visit, VisitService, ServiceAssignment


User = get_user_model()


class VisitWorkflowTests(APITestCase):

    def setUp(self):
        self.client = APIClient()

        # --------------------------------------------------
        # BRANCHES
        # --------------------------------------------------

        self.branch_a = Branch.objects.create(
            name="Kikuyu Branch",
            code="KIK",
            town="Kikuyu",
        )

        self.branch_b = Branch.objects.create(
            name="Second Branch",
            code="BR2",
            town="Nairobi",
        )

        # --------------------------------------------------
        # USERS
        # --------------------------------------------------

        self.admin = User.objects.create_user(
            username="visit_admin",
            email="visit_admin@example.com",
            password="Test-Password-2026!",
            role=User.Role.ADMIN,
        )

        self.supervisor = User.objects.create_user(
            username="visit_supervisor",
            email="visit_supervisor@example.com",
            password="Test-Password-2026!",
            role=User.Role.SUPERVISOR,
        )

        self.detailer = User.objects.create_user(
            username="visit_detailer",
            email="visit_detailer@example.com",
            password="Test-Password-2026!",
            role=User.Role.DETAILER,
        )

        self.cleaner = User.objects.create_user(
            username="visit_cleaner",
            email="visit_cleaner@example.com",
            password="Test-Password-2026!",
            role=User.Role.CLEANER,
        )

        self.cleaner_two = User.objects.create_user(
            username="visit_cleaner_two",
            email="cleaner_two@example.com",
            password="Test-Password-2026!",
            role=User.Role.CLEANER,
        )

        self.other_branch_cleaner = User.objects.create_user(
            username="other_branch_cleaner",
            email="other_cleaner@example.com",
            password="Test-Password-2026!",
            role=User.Role.CLEANER,
        )

        # --------------------------------------------------
        # STAFF PROFILES
        # --------------------------------------------------

        self.supervisor_profile = StaffProfile.objects.create(
            user=self.supervisor,
            staff_number="SUP001",
            branch=self.branch_a,
            date_joined=date(2026, 1, 1),
        )

        self.detailer_profile = StaffProfile.objects.create(
            user=self.detailer,
            staff_number="DET001",
            branch=self.branch_a,
            date_joined=date(2026, 1, 1),
        )

        self.cleaner_profile = StaffProfile.objects.create(
            user=self.cleaner,
            staff_number="CLN001",
            branch=self.branch_a,
            date_joined=date(2026, 1, 1),
        )

        self.cleaner_two_profile = StaffProfile.objects.create(
            user=self.cleaner_two,
            staff_number="CLN002",
            branch=self.branch_a,
            date_joined=date(2026, 1, 1),
        )

        self.other_branch_cleaner_profile = StaffProfile.objects.create(
            user=self.other_branch_cleaner,
            staff_number="CLN003",
            branch=self.branch_b,
            date_joined=date(2026, 1, 1),
        )

        # --------------------------------------------------
        # VEHICLES
        # --------------------------------------------------

        self.vehicle = Vehicle.objects.create(
            registration_number="KDA123A",
            vehicle_type=Vehicle.VehicleType.SALOON,
            branch=self.branch_a,
        )

        self.other_branch_vehicle = Vehicle.objects.create(
            registration_number="KDB456B",
            vehicle_type=Vehicle.VehicleType.SUV,
            branch=self.branch_b,
        )

        # --------------------------------------------------
        # SERVICES
        # --------------------------------------------------

        self.car_wash = Service.objects.create(
            name="Full Car Wash",
            code="FULL-WASH",
            category=Service.Category.CAR_WASH,
            price=Decimal("1000.00"),
            duration_minutes=45,
        )

        self.detailing_service = Service.objects.create(
            name="Interior Detailing",
            code="INTERIOR-DETAIL",
            category=Service.Category.DETAILING,
            price=Decimal("2500.00"),
            duration_minutes=90,
        )

        # --------------------------------------------------
        # URLS
        # --------------------------------------------------

        self.visit_list_url = reverse("visit_list_create")

    # --------------------------------------------------
    # HELPER METHODS
    # --------------------------------------------------

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_visit(self, vehicle=None, user=None):
        vehicle = vehicle or self.vehicle
        user = user or self.admin

        return Visit.objects.create(
            vehicle=vehicle,
            branch=vehicle.branch,
            checked_in_by=user,
        )

    def add_service(self, visit, service=None, user=None):
        service = service or self.car_wash
        user = user or self.admin

        return VisitService.objects.create(
            visit=visit,
            service=service,
            service_name=service.name,
            service_code=service.code,
            service_category=service.category,
            original_price=service.price,
            duration_minutes=service.duration_minutes,
            requires_timer=service.requires_timer,
            added_by=user,
        )

    def service_url(self, visit):
        return reverse(
            "visit_services",
            kwargs={"visit_id": visit.pk},
        )

    def assignment_url(self, visit, visit_service):
        return reverse(
            "service_assignments",
            kwargs={
                "visit_id": visit.pk,
                "visit_service_id": visit_service.pk,
            },
        )

    # --------------------------------------------------
    # VISIT CREATION AND ACCESS
    # --------------------------------------------------

    def test_admin_can_create_visit(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.visit_list_url,
            {
                "vehicle": self.vehicle.pk,
                "branch": self.branch_a.pk,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(Visit.objects.count(), 1)

        visit = Visit.objects.get()

        self.assertEqual(visit.branch, self.branch_a)
        self.assertEqual(visit.vehicle, self.vehicle)
        self.assertEqual(visit.checked_in_by, self.admin)
        self.assertEqual(
            visit.status,
            Visit.Status.CHECKED_IN,
        )

    def test_inactive_vehicle_cannot_be_checked_in(self):
        self.vehicle.is_active = False
        self.vehicle.save()

        self.authenticate(self.admin)

        response = self.client.post(
            self.visit_list_url,
            {
                "vehicle": self.vehicle.pk,
                "branch": self.branch_a.pk,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Visit.objects.count(), 0)

    def test_detailer_can_check_in_vehicle_registered_at_another_branch(self):
        self.authenticate(self.detailer)

        response = self.client.post(
            self.visit_list_url,
            {"vehicle": self.other_branch_vehicle.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        visit = Visit.objects.get()

        # Vehicle registration branch remains unchanged.
        self.assertEqual(
            visit.vehicle.branch,
            self.branch_b,
        )

        # Visit belongs to the detailer's assigned branch.
        self.assertEqual(
            visit.branch,
            self.branch_a,
        )

        self.assertEqual(
            visit.checked_in_by,
            self.detailer,
        )

    def test_cleaner_only_sees_visits_from_assigned_branch(self):
        local_visit = self.create_visit()
        self.create_visit(vehicle=self.other_branch_vehicle)

        self.authenticate(self.cleaner)

        response = self.client.get(self.visit_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            item["id"] for item in response.data
        }

        self.assertIn(local_visit.pk, returned_ids)
        self.assertEqual(len(returned_ids), 1)

    def test_cleaner_cannot_retrieve_visit_from_another_branch(self):
        other_visit = self.create_visit(
            vehicle=self.other_branch_vehicle
        )

        self.authenticate(self.cleaner)

        response = self.client.get(
            reverse(
                "visit_detail",
                kwargs={"pk": other_visit.pk},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # --------------------------------------------------
    # VISIT SERVICES
    # --------------------------------------------------

    def test_supervisor_can_add_service_to_local_visit(self):
        visit = self.create_visit()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.service_url(visit),
            {"service": self.car_wash.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        visit_service = VisitService.objects.get()

        self.assertEqual(visit_service.visit, visit)
        self.assertEqual(visit_service.service, self.car_wash)
        self.assertEqual(
            visit_service.original_price,
            Decimal("1000.00"),
        )
        self.assertEqual(
            visit_service.added_by,
            self.supervisor,
        )

    def test_service_snapshot_is_preserved_after_catalogue_price_changes(self):
        visit = self.create_visit()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.service_url(visit),
            {"service": self.car_wash.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        visit_service = VisitService.objects.get()

        self.car_wash.price = Decimal("1500.00")
        self.car_wash.name = "Updated Full Car Wash"
        self.car_wash.save()

        visit_service.refresh_from_db()

        self.assertEqual(
            visit_service.original_price,
            Decimal("1000.00"),
        )

        self.assertEqual(
            visit_service.service_name,
            "Full Car Wash",
        )

    def test_supervisor_cannot_add_service_to_another_branch_visit(self):
        other_visit = self.create_visit(
            vehicle=self.other_branch_vehicle
        )

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.service_url(other_visit),
            {"service": self.car_wash.pk},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

        self.assertEqual(
            VisitService.objects.filter(visit=other_visit).count(),
            0,
        )

    def test_inactive_service_cannot_be_added(self):
        visit = self.create_visit()

        self.car_wash.is_active = False
        self.car_wash.save()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.service_url(visit),
            {"service": self.car_wash.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(VisitService.objects.count(), 0)

    def test_service_cannot_be_added_to_completed_visit(self):
        visit = self.create_visit()

        visit.status = Visit.Status.COMPLETED
        visit.save()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.service_url(visit),
            {"service": self.car_wash.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(VisitService.objects.count(), 0)

    # --------------------------------------------------
    # STAFF ASSIGNMENTS
    # --------------------------------------------------

    def test_supervisor_can_assign_cleaner_to_car_wash(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.cleaner_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        assignment = ServiceAssignment.objects.get()

        self.assertEqual(
            assignment.staff,
            self.cleaner_profile,
        )

        self.assertEqual(
            assignment.assigned_by,
            self.supervisor,
        )

        self.assertTrue(assignment.is_active)

    def test_detailer_cannot_be_assigned_to_car_wash(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.detailer_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ServiceAssignment.objects.count(), 0)

    def test_staff_from_another_branch_cannot_be_assigned(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.other_branch_cleaner_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ServiceAssignment.objects.count(), 0)

    def test_inactive_staff_cannot_be_assigned(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        self.cleaner_profile.employment_status = (
            StaffProfile.EmploymentStatus.INACTIVE
        )
        self.cleaner_profile.save()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.cleaner_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ServiceAssignment.objects.count(), 0)

    def test_same_cleaner_cannot_be_assigned_twice(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        ServiceAssignment.objects.create(
            visit_service=visit_service,
            staff=self.cleaner_profile,
            assigned_by=self.supervisor,
        )

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.cleaner_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ServiceAssignment.objects.count(), 1)

    def test_assignment_can_be_removed_without_deleting_history(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        assignment = ServiceAssignment.objects.create(
            visit_service=visit_service,
            staff=self.cleaner_profile,
            assigned_by=self.supervisor,
        )

        self.authenticate(self.supervisor)

        url = reverse(
            "remove_service_assignment",
            kwargs={
                "visit_id": visit.pk,
                "visit_service_id": visit_service.pk,
                "assignment_id": assignment.pk,
            },
        )

        response = self.client.post(
            url,
            {"removal_reason": "Incorrect assignment"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        assignment.refresh_from_db()

        self.assertFalse(assignment.is_active)
        self.assertIsNotNone(assignment.removed_at)
        self.assertEqual(
            assignment.removed_by,
            self.supervisor,
        )
        self.assertEqual(
            assignment.removal_reason,
            "Incorrect assignment",
        )

        # The original record must remain in the database.
        self.assertTrue(
            ServiceAssignment.objects.filter(
                pk=assignment.pk
            ).exists()
        )

    def test_staff_cannot_be_assigned_to_completed_visit(self):
        visit = self.create_visit()
        visit_service = self.add_service(visit)

        visit.status = Visit.Status.COMPLETED
        visit.save()

        self.authenticate(self.supervisor)

        response = self.client.post(
            self.assignment_url(visit, visit_service),
            {"staff": self.cleaner_profile.pk},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ServiceAssignment.objects.count(), 0)
