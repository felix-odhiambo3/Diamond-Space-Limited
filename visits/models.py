
from django.conf import settings
from django.db import models

from branches.models import Branch
from vehicles.models import Vehicle
from services.models import Service
from staff.models import StaffProfile


class Visit(models.Model):

    class Status(models.TextChoices):
        CHECKED_IN = 'CHECKED_IN', 'Checked In'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='visits'
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='visits'
    )

    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='vehicle_checkins'
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CHECKED_IN
    )

    arrival_time = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    plastic_mat_count = models.PositiveIntegerField(default=0)
    woolen_mat_count = models.PositiveIntegerField(default=0)

    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-arrival_time']

    def __str__(self):
        return f"{self.vehicle.registration_number} - Visit #{self.id}"


class VisitService(models.Model):

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name='visit_services'
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='visit_records'
    )

    # Historical snapshots: preserve the service details
    # even if the catalogue changes later.
    service_name = models.CharField(max_length=150)
    service_code = models.CharField(max_length=30)
    service_category = models.CharField(max_length=20)

    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    requires_timer = models.BooleanField(default=True)

    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='added_visit_services'
    )

    added_at = models.DateTimeField(auto_now_add=True)

    # Preserve removal history instead of deleting records.
    is_removed = models.BooleanField(default=False)
    removed_at = models.DateTimeField(null=True, blank=True)

    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='removed_visit_services',
        null=True,
        blank=True
    )

    removal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['added_at']

    def __str__(self):
        return f"{self.service_name} - Visit #{self.visit_id}"


class ServiceAssignment(models.Model):
    visit_service = models.ForeignKey(
        VisitService,
        on_delete=models.PROTECT,
        related_name='assignments'
    )

    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.PROTECT,
        related_name='service_assignments'
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='made_service_assignments'
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    removed_at = models.DateTimeField(null=True, blank=True)

    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='removed_service_assignments',
        null=True,
        blank=True
    )

    removal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=['visit_service', 'staff'],
                condition=models.Q(is_active=True),
                name='unique_active_staff_service_assignment'
            )
        ]

    def __str__(self):
        return (
            f"{self.staff.staff_number} assigned to "
            f"{self.visit_service.service_name}"
        )
