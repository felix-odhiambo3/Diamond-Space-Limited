from django.conf import settings
from django.db import models
from branches.models import Branch


class StaffProfile(models.Model):

    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='staff_profile'
    )

    staff_number = models.CharField(
        max_length=30,
        unique=True
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name='staff_members'
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE
    )

    date_joined = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['staff_number']

    def __str__(self):
        return f"{self.staff_number} - {self.user.get_full_name()}"


class ShiftAssignment(models.Model):

    class Shift(models.TextChoices):
        DAY = 'DAY', 'Day'
        NIGHT = 'NIGHT', 'Night'

    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.PROTECT,
        related_name='shift_assignments'
    )

    shift = models.CharField(
        max_length=10,
        choices=Shift.choices
    )

    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True,
        blank=True
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='shift_changes'
    )

    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.staff.staff_number} - {self.shift}"