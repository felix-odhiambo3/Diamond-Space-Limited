
from django.conf import settings
from django.db import models
from django.db.models import Q


class ShiftConfiguration(models.Model):
    class ShiftType(models.TextChoices):
        DAY = "DAY", "Day"
        NIGHT = "NIGHT", "Night"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="shift_configurations",
    )
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    early_check_in_minutes = models.PositiveSmallIntegerField(default=30)
    late_grace_minutes = models.PositiveSmallIntegerField(default=15)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["branch", "shift_type", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "shift_type"],
                condition=Q(is_active=True),
                name="unique_active_branch_shift_config",
            ),
            models.UniqueConstraint(
                fields=["branch", "shift_type", "version"],
                name="unique_branch_shift_config_version",
            ),
        ]

    def __str__(self):
        return f"{self.branch} - {self.get_shift_type_display()}"


class ShiftInstance(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FINALIZED = "FINALIZED", "Finalized"

    configuration = models.ForeignKey(
        ShiftConfiguration,
        on_delete=models.PROTECT,
        related_name="shift_instances",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="shift_instances",
    )
    shift_type = models.CharField(
        max_length=10,
        choices=ShiftConfiguration.ShiftType.choices,
    )
    work_date = models.DateField(
        help_text="Local Nairobi date on which this shift starts.",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    configuration_snapshot = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "shift_type", "work_date"],
                name="unique_branch_shift_instance_date",
            ),
            models.CheckConstraint(
                condition=Q(scheduled_end__gt=models.F("scheduled_start")),
                name="shift_instance_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.branch} - {self.shift_type} - {self.work_date}"


class ShiftAttendanceAuthorization(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="shift_attendance_authorizations",
    )
    shift_instance = models.ForeignKey(
        ShiftInstance,
        on_delete=models.PROTECT,
        related_name="attendance_authorizations",
    )
    permanent_shift_assignment = models.ForeignKey(
        "staff.ShiftAssignment",
        on_delete=models.PROTECT,
        related_name="attendance_authorizations",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_shift_authorizations",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_shift_authorizations",
        null=True,
        blank=True,
    )
    reviewer_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "shift_instance"],
                name="unique_staff_shift_authorization",
            ),
        ]

    def __str__(self):
        return f"{self.staff.staff_number} - {self.shift_instance} - {self.status}"


class AttendanceRecord(models.Model):
    class AttendanceStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ON_TIME = "ON_TIME", "On Time"
        LATE = "LATE", "Late"
        ABSENT = "ABSENT", "Absent"

    class CheckoutStatus(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        OPEN = "OPEN", "Clocked In"
        MANUAL = "MANUAL", "Manual Checkout"
        AUTO = "AUTO", "Automatic Checkout"

    class VerificationStatus(models.TextChoices):
        VERIFIED = "VERIFIED", "GPS Verified"
        OVERRIDE = "OVERRIDE", "Supervisor Override"

    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    shift_instance = models.ForeignKey(
    ShiftInstance,
    on_delete=models.PROTECT,
    related_name="attendance_records",
    null=True,
    blank=True,
    )
    shift_assignment = models.ForeignKey(
        "staff.ShiftAssignment",
        on_delete=models.PROTECT,
        related_name="attendance_records",
        help_text="Permanent shift assignment applicable to this employee.",
    )
    shift_authorization = models.ForeignKey(
        ShiftAttendanceAuthorization,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        null=True,
        blank=True,
    )

    attendance_status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PENDING,
    )
    checkout_status = models.CharField(
        max_length=20,
        choices=CheckoutStatus.choices,
        default=CheckoutStatus.NOT_STARTED,
    )

    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)

    clock_in_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assisted_attendance_checkins",
        null=True,
        blank=True,
    )
    clock_in_recorded_at = models.DateTimeField(null=True, blank=True)
    clock_in_assisted_reason = models.TextField(blank=True)

    clock_out_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assisted_attendance_checkouts",
        null=True,
        blank=True,
    )
    clock_out_recorded_at = models.DateTimeField(null=True, blank=True)
    clock_out_assisted_reason = models.TextField(blank=True)

    clock_in_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    clock_in_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    clock_in_accuracy = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    clock_in_distance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    clock_out_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    clock_out_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    clock_out_accuracy = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    clock_out_distance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    clock_in_verification = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        null=True,
        blank=True,
    )
    clock_out_verification = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        null=True,
        blank=True,
    )

    clock_in_ip_address = models.GenericIPAddressField(null=True, blank=True)
    clock_out_ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-shift_instance__scheduled_start", "staff__staff_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "shift_instance"],
                name="unique_staff_attendance_instance",
            ),

            # Checkout timestamps must match checkout status.
            models.CheckConstraint(
                condition=(
                    Q(
                        checkout_status="NOT_STARTED",
                        clock_out__isnull=True,
                    )
                    | Q(
                        checkout_status="OPEN",
                        clock_in__isnull=False,
                        clock_out__isnull=True,
                    )
                    | Q(
                        checkout_status__in=["MANUAL", "AUTO"],
                        clock_in__isnull=False,
                        clock_out__isnull=False,
                    )
                ),
                name="attendance_checkout_timestamp_consistency",
            ),

            # Clock-out must happen after clock-in.
            models.CheckConstraint(
                condition=(
                    Q(clock_in__isnull=True)
                    | Q(clock_out__isnull=True)
                    | Q(clock_out__gt=models.F("clock_in"))
                ),
                name="attendance_checkout_after_checkin",
            ),

            # Pending and absent employees cannot have clock-in timestamps.
            models.CheckConstraint(
                condition=(
                    Q(
                        attendance_status__in=["PENDING", "ABSENT"],
                        clock_in__isnull=True,
                        clock_out__isnull=True,
                        checkout_status="NOT_STARTED",
                    )
                    | Q(
                        attendance_status__in=["ON_TIME", "LATE"],
                        clock_in__isnull=False,
                        checkout_status__in=["OPEN", "MANUAL", "AUTO"],
                    )
                ),
                name="attendance_status_timestamp_consistency",
            ),
        ]

    def __str__(self):
        return (
            f"{self.staff.staff_number} - "
            f"{self.shift_instance} - {self.attendance_status}"
        )


class AttendanceOverrideRequest(models.Model):
    class Action(models.TextChoices):
        CLOCK_IN = "CLOCK_IN", "Clock In"
        CLOCK_OUT = "CLOCK_OUT", "Clock Out"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        related_name="override_requests",
        null=True,
        blank=True,
    )
    shift_instance = models.ForeignKey(
        ShiftInstance,
        on_delete=models.PROTECT,
        related_name="override_requests",
        null=True,
        blank=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_attendance_overrides",
        null=True,
        blank=True,
    )
    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="attendance_override_requests",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="attendance_override_requests",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    accuracy = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    employee_reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_attendance_overrides",
        null=True,
        blank=True,
    )
    reviewer_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.staff.staff_number} - {self.action} - {self.status}"


class AttendanceAuditLog(models.Model):
    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    shift_instance = models.ForeignKey(
        ShiftInstance,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_audit_logs",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.created_at}"


class ShiftReport(models.Model):
    shift_instance = models.OneToOneField(
        ShiftInstance,
        on_delete=models.PROTECT,
        related_name="report",
    )
    report_data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finalized_shift_reports",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"Report - {self.shift_instance}"
