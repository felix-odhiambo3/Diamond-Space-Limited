
from django.conf import settings
from django.db import models
from django.db.models import Q


class AttendanceRecord(models.Model):

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Clocked In'
        COMPLETED = 'COMPLETED', 'Completed'

    class VerificationStatus(models.TextChoices):
        VERIFIED = 'VERIFIED', 'GPS Verified'
        OVERRIDE = 'OVERRIDE', 'Supervisor Override'

    staff = models.ForeignKey(
        'staff.StaffProfile',
        on_delete=models.PROTECT,
        related_name='attendance_records'
    )

    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.PROTECT,
        related_name='attendance_records'
    )

    shift_assignment = models.ForeignKey(
        'staff.ShiftAssignment',
        on_delete=models.PROTECT,
        related_name='attendance_records'
    )

    work_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )

    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)

    # Clock-in GPS information
    clock_in_latitude = models.DecimalField(
        max_digits=10, decimal_places=7
    )
    clock_in_longitude = models.DecimalField(
        max_digits=10, decimal_places=7
    )
    clock_in_accuracy = models.DecimalField(
        max_digits=8, decimal_places=2
    )
    clock_in_distance = models.DecimalField(
        max_digits=10, decimal_places=2
    )

    # Clock-out GPS information
    clock_out_latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    clock_out_longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    clock_out_accuracy = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    clock_out_distance = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    clock_in_verification = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.VERIFIED
    )

    clock_out_verification = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        null=True,
        blank=True
    )

    clock_in_ip_address = models.GenericIPAddressField(
        null=True, blank=True
    )
    clock_out_ip_address = models.GenericIPAddressField(
        null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_date', '-clock_in']
        constraints = [
            models.UniqueConstraint(
                fields=['staff', 'work_date', 'shift_assignment'],
                name='unique_staff_attendance_shift'
            ),
            models.CheckConstraint(
                condition=(
                    Q(status='OPEN', clock_out__isnull=True)
                    | Q(status='COMPLETED', clock_out__isnull=False)
                ),
                name='attendance_status_clockout_consistency'
            ),
        ]

    def __str__(self):
        return (
            f"{self.staff.staff_number} - "
            f"{self.work_date} - {self.status}"
        )


class AttendanceOverrideRequest(models.Model):

    class Action(models.TextChoices):
        CLOCK_IN = 'CLOCK_IN', 'Clock In'
        CLOCK_OUT = 'CLOCK_OUT', 'Clock Out'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        related_name='override_requests',
        null=True,
        blank=True
    )

    staff = models.ForeignKey(
        'staff.StaffProfile',
        on_delete=models.PROTECT,
        related_name='attendance_override_requests'
    )

    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.PROTECT,
        related_name='attendance_override_requests'
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices
    )

    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    accuracy = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )

    employee_reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_attendance_overrides',
        null=True,
        blank=True
    )

    reviewer_reason = models.TextField(blank=True)

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.staff.staff_number} - "
            f"{self.action} - {self.status}"
        )
