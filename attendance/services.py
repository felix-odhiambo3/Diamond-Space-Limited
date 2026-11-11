
import math
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from staff.models import StaffProfile, ShiftAssignment

from .models import (
    AttendanceRecord,
    AttendanceAuditLog,
    AttendanceOverrideRequest,
    ShiftConfiguration,
    ShiftInstance,
    ShiftAttendanceAuthorization,
)


MAX_GPS_ACCURACY_METRES = Decimal("50.00")


class AttendanceError(Exception):
    """Raised when an attendance operation violates a business rule."""
    pass


def calculate_distance_metres(
    latitude1,
    longitude1,
    latitude2,
    longitude2,
):
    """Calculate the distance between two GPS coordinates using Haversine."""

    earth_radius = 6371000

    lat1 = math.radians(float(latitude1))
    lon1 = math.radians(float(longitude1))
    lat2 = math.radians(float(latitude2))
    lon2 = math.radians(float(longitude2))

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius * c


def validate_gps_location(
    *,
    branch,
    latitude,
    longitude,
    accuracy,
):
    """Validate GPS coordinates, accuracy and branch geofence."""

    try:
        latitude = Decimal(str(latitude))
        longitude = Decimal(str(longitude))
        accuracy = Decimal(str(accuracy))
    except Exception:
        raise AttendanceError("Invalid GPS information.")

    if not latitude.is_finite() or not longitude.is_finite():
        raise AttendanceError(
            "GPS coordinates must be finite numbers."
        )

    if not accuracy.is_finite():
        raise AttendanceError(
            "GPS accuracy must be a finite number."
        )

    if not -90 <= latitude <= 90:
        raise AttendanceError("Invalid latitude.")

    if not -180 <= longitude <= 180:
        raise AttendanceError("Invalid longitude.")

    if accuracy <= 0:
        raise AttendanceError(
            "GPS accuracy must be greater than zero."
        )

    if accuracy > MAX_GPS_ACCURACY_METRES:
        raise AttendanceError(
            "GPS accuracy is insufficient. "
            "Please enable precise location and try again."
        )

    if branch.latitude is None or branch.longitude is None:
        raise AttendanceError(
            "This branch has not been configured for GPS attendance."
        )

    if not branch.is_active:
        raise AttendanceError("This branch is inactive.")

    distance = calculate_distance_metres(
        latitude,
        longitude,
        branch.latitude,
        branch.longitude,
    )

    if distance > branch.attendance_radius:
        raise AttendanceError(
            "You are outside the permitted attendance area. "
            f"Your distance is approximately {distance:.2f} metres."
        )

    return {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "distance": Decimal(str(round(distance, 2))),
    }


def get_active_shift_assignment(staff, work_date):
    """Find the employee's applicable shift assignment for a date."""

    assignment = (
        ShiftAssignment.objects
        .filter(
            staff=staff,
            effective_from__lte=work_date,
        )
        .filter(
            models.Q(effective_to__isnull=True)
            | models.Q(effective_to__gte=work_date)
        )
        .order_by("-effective_from", "-created_at")
        .first()
    )

    if not assignment:
        raise AttendanceError(
            "You do not have an active shift assignment for this date."
        )

    return assignment


@transaction.atomic
def get_or_create_shift_instance(
    *,
    branch,
    shift_type,
    work_date,
):
    """
    Retrieve an existing shift instance or create a new one.

    DAY:   07:00–19:00 on the same date.
    NIGHT: 19:00–07:00 on the following date.

    Existing instances retain their original configuration snapshot.
    """

    if shift_type not in ("DAY", "NIGHT"):
        raise AttendanceError("Invalid shift type.")

    existing_instance = (
        ShiftInstance.objects
        .select_for_update()
        .filter(
            branch=branch,
            shift_type=shift_type,
            work_date=work_date,
        )
        .first()
    )

    if existing_instance:
        return existing_instance, False

    configuration = (
        ShiftConfiguration.objects
        .filter(
            branch=branch,
            shift_type=shift_type,
            is_active=True,
        )
        .order_by("-version")
        .first()
    )

    if not configuration:
        raise AttendanceError(
            f"No active {shift_type} shift configuration exists "
            f"for branch {branch.name}."
        )

    end_date = (
        work_date
        if shift_type == "DAY"
        else work_date + timedelta(days=1)
    )

    tz = timezone.get_current_timezone()

    scheduled_start = timezone.make_aware(
        datetime.combine(
            work_date,
            configuration.start_time,
        ),
        tz,
    )

    scheduled_end = timezone.make_aware(
        datetime.combine(
            end_date,
            configuration.end_time,
        ),
        tz,
    )

    if scheduled_end <= scheduled_start:
        raise AttendanceError(
            "The configured shift end time must be after its start time."
        )

    snapshot = {
        "configuration_id": configuration.id,
        "version": configuration.version,
        "shift_type": configuration.shift_type,
        "start_time": configuration.start_time.isoformat(),
        "end_time": configuration.end_time.isoformat(),
        "early_check_in_minutes": configuration.early_check_in_minutes,
        "late_grace_minutes": configuration.late_grace_minutes,
        "branch_id": branch.id,
        "branch_name": branch.name,
    }

    instance, created = ShiftInstance.objects.get_or_create(
        branch=branch,
        shift_type=shift_type,
        work_date=work_date,
        defaults={
            "configuration": configuration,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "configuration_snapshot": snapshot,
            "status": ShiftInstance.Status.SCHEDULED,
        },
    )

    return instance, created



@transaction.atomic
def clock_in(
    *,
    user,
    latitude,
    longitude,
    accuracy,
    shift_type=None,
    ip_address=None,
):
    """Record a GPS-verified employee clock-in."""

    try:
        staff = (
            StaffProfile.objects
            .select_for_update()
            .select_related("branch", "user")
            .get(user=user)
        )
    except StaffProfile.DoesNotExist:
        raise AttendanceError(
            "Your account is not linked to a staff profile."
        )

    if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
        raise AttendanceError(
            "Your employment status does not permit attendance."
        )

    branch = staff.branch

    if not branch.is_active:
        raise AttendanceError("This branch is inactive.")

    now = timezone.now()
    today = timezone.localdate(now)

    if shift_type is not None and shift_type not in ("DAY", "NIGHT"):
        raise AttendanceError("Invalid shift type.")

    candidate_dates = [
        today,
        today - timedelta(days=1),
    ]

    eligible_shift = None
    assignment = None

    for work_date in candidate_dates:
        try:
            current_assignment = get_active_shift_assignment(
                staff,
                work_date,
            )
        except AttendanceError:
            continue

        requested_shift = shift_type or current_assignment.shift

        instance, _ = get_or_create_shift_instance(
            branch=branch,
            shift_type=requested_shift,
            work_date=work_date,
        )

        early_minutes = int(
            instance.configuration_snapshot.get(
                "early_check_in_minutes",
                30,
            )
        )

        earliest_clock_in = (
            instance.scheduled_start
            - timedelta(minutes=early_minutes)
        )

        if earliest_clock_in <= now < instance.scheduled_end:
            eligible_shift = instance
            assignment = current_assignment
            break

    if not eligible_shift:
        raise AttendanceError(
            "No assigned shift is currently available for clock-in. "
            "You may clock in up to 30 minutes before your shift starts."
        )

    # Lock the shift instance before checking its status.
    try:
        shift_instance = (
            ShiftInstance.objects
            .select_for_update()
            .get(pk=eligible_shift.pk)
        )
    except ShiftInstance.DoesNotExist:
        raise AttendanceError(
            "The selected shift instance no longer exists."
        )

    authorization = None

    # Different shifts require supervisor authorization.
    if shift_instance.shift_type != assignment.shift:
        authorization = (
            ShiftAttendanceAuthorization.objects
            .select_for_update()
            .filter(
                staff=staff,
                shift_instance=shift_instance,
                permanent_shift_assignment=assignment,
            )
            .first()
        )

        if not authorization or authorization.status != "APPROVED":
            raise AttendanceError(
                "You are not authorized to work this shift. "
                "Please request supervisor approval."
            )

        if not authorization.reviewed_by:
            raise AttendanceError(
                "The shift authorization has no recorded reviewer."
            )

    # Completed and finalized shifts cannot accept new clock-ins.
    if shift_instance.status in (
        ShiftInstance.Status.COMPLETED,
        ShiftInstance.Status.FINALIZED,
    ):
        raise AttendanceError(
            "This shift is already completed or finalized."
        )

    # Verify GPS location.
    gps = validate_gps_location(
        branch=branch,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    # Prevent duplicate attendance.
    existing_record = AttendanceRecord.objects.filter(
        staff=staff,
        shift_instance=shift_instance,
    ).first()

    if existing_record:
        if existing_record.checkout_status == "OPEN":
            raise AttendanceError(
                "You are already clocked in for this shift."
            )

        raise AttendanceError(
            "Attendance has already been recorded for this shift."
        )

    grace_minutes = int(
        shift_instance.configuration_snapshot.get(
            "late_grace_minutes",
            15,
        )
    )

    late_deadline = (
        shift_instance.scheduled_start
        + timedelta(minutes=grace_minutes)
    )

    attendance_status = (
        AttendanceRecord.AttendanceStatus.LATE
        if now > late_deadline
        else AttendanceRecord.AttendanceStatus.ON_TIME
    )

    record = AttendanceRecord.objects.create(
        staff=staff,
        branch=branch,
        shift_instance=shift_instance,
        shift_assignment=assignment,
        shift_authorization=authorization,
        attendance_status=attendance_status,
        checkout_status=AttendanceRecord.CheckoutStatus.OPEN,
        clock_in=now,
        clock_in_latitude=gps["latitude"],
        clock_in_longitude=gps["longitude"],
        clock_in_accuracy=gps["accuracy"],
        clock_in_distance=gps["distance"],
        clock_in_verification=(
            AttendanceRecord.VerificationStatus.VERIFIED
        ),
        clock_in_ip_address=ip_address,
    )

    # Start the shift when its first employee clocks in.
    if shift_instance.status == ShiftInstance.Status.SCHEDULED:
        shift_instance.status = ShiftInstance.Status.IN_PROGRESS
        shift_instance.save(update_fields=["status", "updated_at"])

        AttendanceAuditLog.objects.create(
            attendance=record,
            shift_instance=shift_instance,
            action="SHIFT_STARTED",
            old_values={
                "status": ShiftInstance.Status.SCHEDULED,
            },
            new_values={
                "status": ShiftInstance.Status.IN_PROGRESS,
                "shift_instance_id": shift_instance.id,
                "triggered_by_attendance_id": record.id,
            },
            actor=user,
            reason="Shift automatically started by the first employee clock-in.",
        )

    AttendanceAuditLog.objects.create(
        attendance=record,
        shift_instance=shift_instance,
        action="EMPLOYEE_CLOCK_IN",
        old_values={
            "attendance_status": "PENDING",
            "checkout_status": "NOT_STARTED",
        },
        new_values={
            "attendance_id": record.id,
            "staff_id": staff.id,
            "shift_instance_id": shift_instance.id,
            "attendance_status": attendance_status,
            "checkout_status": "OPEN",
            "clock_in": now.isoformat(),
            "gps_distance_metres": str(gps["distance"]),
            "verification": "VERIFIED",
        },
        actor=user,
        reason="Employee self-service GPS-verified clock-in.",
    )

    return record



@transaction.atomic
def clock_out(
    *,
    user,
    latitude,
    longitude,
    accuracy,
    ip_address=None,
):
    """Record an employee's GPS-verified manual clock-out."""

    try:
        staff = (
            StaffProfile.objects
            .select_for_update()
            .select_related("branch", "user")
            .get(user=user)
        )
    except StaffProfile.DoesNotExist:
        raise AttendanceError(
            "Your account is not linked to a staff profile."
        )

    # Lock attendance records without locking nullable joined relations.
    open_records = list(
       AttendanceRecord.objects
       .select_for_update(of=("self",))
       .filter(
           staff=staff,
           checkout_status=AttendanceRecord.CheckoutStatus.OPEN,
       )
   )

    if not open_records:
        raise AttendanceError(
            "You do not have an active clock-in to check out."
        )

    if len(open_records) > 1:
        raise AttendanceError(
            "Multiple open attendance records were found. "
            "Please contact your supervisor."
        )

    record = open_records[0]
    now = timezone.now()

    if not record.clock_in:
        raise AttendanceError(
            "This attendance record has no valid clock-in timestamp."
        )

    if now <= record.clock_in:
        raise AttendanceError(
            "Clock-out time must be later than clock-in time."
        )

    if (
        record.shift_instance_id
        and record.shift_instance.status == ShiftInstance.Status.FINALIZED
    ):
        raise AttendanceError(
            "This shift has already been finalized."
        )

    # Verify GPS location against the employee's assigned branch.
    gps = validate_gps_location(
        branch=record.branch,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    old_values = {
        "checkout_status": record.checkout_status,
        "clock_out": (
            record.clock_out.isoformat()
            if record.clock_out else None
        ),
    }

    # Normal employee self-service checkout.
    record.clock_out = now
    record.checkout_status = AttendanceRecord.CheckoutStatus.MANUAL

    record.clock_out_latitude = gps["latitude"]
    record.clock_out_longitude = gps["longitude"]
    record.clock_out_accuracy = gps["accuracy"]
    record.clock_out_distance = gps["distance"]

    record.clock_out_verification = (
        AttendanceRecord.VerificationStatus.VERIFIED
    )

    record.clock_out_ip_address = ip_address

    # These fields are reserved for supervisor-assisted checkout.
    record.clock_out_recorded_by = None
    record.clock_out_recorded_at = None
    record.clock_out_assisted_reason = ""

    record.save()

    # Record the checkout in the audit log.
    AttendanceAuditLog.objects.create(
        attendance=record,
        shift_instance=record.shift_instance,
        action="EMPLOYEE_CLOCK_OUT",
        old_values=old_values,
        new_values={
            "attendance_id": record.id,
            "staff_id": staff.id,
            "checkout_status": "MANUAL",
            "clock_out": now.isoformat(),
            "gps_distance_metres": str(gps["distance"]),
            "verification": "VERIFIED",
            "assisted": False,
        },
        actor=user,
        reason="Employee self-service GPS-verified clock-out.",
    )

    return record


@transaction.atomic
def create_attendance_override_request(
    *,
    requested_by,
    staff_id,
    shift_instance_id,
    action,
    reason,
    latitude=None,
    longitude=None,
    accuracy=None,
):
    """
    Create a supervisor-initiated assisted attendance request.

    Only OWNER, ADMIN and SUPERVISOR accounts may initiate requests.
    Supervisors are restricted to their own branch.
    """

    allowed_roles = {"OWNER", "ADMIN", "SUPERVISOR"}

    if not requested_by or not requested_by.is_authenticated:
        raise AttendanceError("Authentication is required.")

    if not (
        requested_by.is_superuser
        or requested_by.role in allowed_roles
    ):
        raise AttendanceError(
            "You are not authorized to create attendance override requests."
        )

    action = str(action).upper()

    if action not in (
        AttendanceOverrideRequest.Action.CLOCK_IN,
        AttendanceOverrideRequest.Action.CLOCK_OUT,
    ):
        raise AttendanceError("Invalid attendance override action.")

    reason = (reason or "").strip()

    if not reason:
        raise AttendanceError(
            "A reason is required for an attendance override."
        )

    try:
        staff = (
            StaffProfile.objects
            .select_for_update()
            .select_related("branch", "user")
            .get(pk=staff_id)
        )
    except StaffProfile.DoesNotExist:
        raise AttendanceError("Staff member does not exist.")

    if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
        raise AttendanceError(
            "Only active employees can receive assisted attendance."
        )

    branch = staff.branch

    if not branch.is_active:
        raise AttendanceError("The employee's branch is inactive.")

    # Supervisors can only create requests within their own branch.
    if (
        requested_by.role == "SUPERVISOR"
        and not requested_by.is_superuser
    ):
        try:
            supervisor_profile = StaffProfile.objects.get(
                user=requested_by
            )
        except StaffProfile.DoesNotExist:
            raise AttendanceError(
                "Your account is not linked to a staff profile."
            )

        if supervisor_profile.branch_id != branch.id:
            raise AttendanceError(
                "You can only create requests for staff in your branch."
            )

    try:
        shift_instance = (
            ShiftInstance.objects
            .select_for_update()
            .select_related("branch")
            .get(pk=shift_instance_id)
        )
    except ShiftInstance.DoesNotExist:
        raise AttendanceError("Shift instance does not exist.")

    if shift_instance.branch_id != branch.id:
        raise AttendanceError(
            "The selected shift does not belong to the employee's branch."
        )

    if shift_instance.status == ShiftInstance.Status.FINALIZED:
        raise AttendanceError(
            "This shift has already been finalized."
        )

    now = timezone.now()

    # Validate optional GPS evidence without treating it as verified.
    gps_values = (latitude, longitude, accuracy)

    if any(value is not None for value in gps_values):
        if any(value is None for value in gps_values):
            raise AttendanceError(
                "GPS latitude, longitude and accuracy must be supplied together."
            )

        try:
            latitude = Decimal(str(latitude))
            longitude = Decimal(str(longitude))
            accuracy = Decimal(str(accuracy))
        except Exception:
            raise AttendanceError("Invalid GPS information.")

        if (
            not latitude.is_finite()
            or not longitude.is_finite()
            or not accuracy.is_finite()
        ):
            raise AttendanceError(
                "GPS values must be finite numbers."
            )

        if not -90 <= latitude <= 90:
            raise AttendanceError("Invalid GPS latitude.")

        if not -180 <= longitude <= 180:
            raise AttendanceError("Invalid GPS longitude.")

        if accuracy <= 0:
            raise AttendanceError(
                "GPS accuracy must be greater than zero."
            )

    attendance = None

    if action == AttendanceOverrideRequest.Action.CLOCK_IN:

        if shift_instance.status == ShiftInstance.Status.COMPLETED:
            raise AttendanceError(
                "A completed shift cannot accept new clock-ins."
            )

        early_minutes = int(
            shift_instance.configuration_snapshot.get(
                "early_check_in_minutes",
                30,
            )
        )

        earliest_clock_in = (
            shift_instance.scheduled_start
            - timedelta(minutes=early_minutes)
        )

        if not earliest_clock_in <= now < shift_instance.scheduled_end:
            raise AttendanceError(
                "Assisted clock-in is only permitted during the "
                "configured shift attendance window."
            )

        try:
            assignment = get_active_shift_assignment(
                staff,
                shift_instance.work_date,
            )
        except AttendanceError:
            raise AttendanceError(
                "The employee has no valid shift assignment for this date."
            )

        if assignment.shift != shift_instance.shift_type:
            authorization = (
                ShiftAttendanceAuthorization.objects
                .filter(
                    staff=staff,
                    shift_instance=shift_instance,
                    permanent_shift_assignment=assignment,
                    status="APPROVED",
                )
                .first()
            )

            if not authorization or not authorization.reviewed_by:
                raise AttendanceError(
                    "The employee requires an approved authorization "
                    "to work this different shift."
                )

        existing_record = AttendanceRecord.objects.filter(
            staff=staff,
            shift_instance=shift_instance,
        ).first()

        if existing_record:
            raise AttendanceError(
                "Attendance has already been recorded for this shift."
            )

    else:
        # Clock-out must refer to the employee's current open attendance.
        open_records = list(
            AttendanceRecord.objects
            .select_for_update(of=("self",))
            .filter(
                staff=staff,
                checkout_status=AttendanceRecord.CheckoutStatus.OPEN,
            )
        )

        if not open_records:
            raise AttendanceError(
                "The employee has no active clock-in to check out."
            )

        if len(open_records) != 1:
            raise AttendanceError(
                "Multiple open attendance records exist. "
                "Please resolve them before creating an override."
            )

        attendance = open_records[0]

        if attendance.shift_instance_id != shift_instance.id:
            raise AttendanceError(
                "The selected shift does not match the employee's open attendance."
            )

        if attendance.clock_in and now <= attendance.clock_in:
            raise AttendanceError(
                "Clock-out must happen after clock-in."
            )

    # Prevent duplicate pending requests for the same action and shift.
    pending_request = AttendanceOverrideRequest.objects.filter(
        staff=staff,
        shift_instance=shift_instance,
        action=action,
        status=AttendanceOverrideRequest.Status.PENDING,
    ).exists()

    if pending_request:
        raise AttendanceError(
            "A pending override request already exists for this action and shift."
        )

    override_request = AttendanceOverrideRequest.objects.create(
        attendance=attendance,
        requested_by=requested_by,
        staff=staff,
        branch=branch,
        shift_instance=shift_instance,
        action=action,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        employee_reason=reason,
        status=AttendanceOverrideRequest.Status.PENDING,
    )

    return override_request



@transaction.atomic
def review_attendance_override_request(
    *,
    reviewed_by,
    request_id,
    decision,
    reason,
):
    """
    Approve or reject a supervisor-assisted attendance request.

    The reviewer must be different from the requester.
    Supervisors can only review requests within their own branch.
    Approval does not execute the attendance action.
    """

    allowed_roles = {"OWNER", "ADMIN", "SUPERVISOR"}

    if not reviewed_by or not reviewed_by.is_authenticated:
        raise AttendanceError("Authentication is required.")

    if not (
        reviewed_by.is_superuser
        or reviewed_by.role in allowed_roles
    ):
        raise AttendanceError(
            "You are not authorized to review attendance override requests."
        )

    decision = str(decision).upper().strip()

    if decision not in ("APPROVE", "REJECT"):
        raise AttendanceError(
            "Decision must be APPROVE or REJECT."
        )

    reason = (reason or "").strip()

    if not reason:
        raise AttendanceError(
            "A review reason is required."
        )

    try:
        override_request = (
            AttendanceOverrideRequest.objects
            .select_for_update(of=("self",))
            .select_related(
                "requested_by",
                "staff",
                "branch",
                "shift_instance",
                "attendance",
            )
          .get(pk=request_id)
      )
    except AttendanceOverrideRequest.DoesNotExist:
        raise AttendanceError(
            "Attendance override request does not exist."
        )

    if override_request.status != AttendanceOverrideRequest.Status.PENDING:
        raise AttendanceError(
            "This request has already been reviewed."
        )

    # Prevent self-approval and self-rejection.
    if (
        override_request.requested_by_id
        and override_request.requested_by_id == reviewed_by.id
    ):
        raise AttendanceError(
            "You cannot review your own attendance override request."
        )

    # Supervisors may only review requests within their own branch.
    if (
        reviewed_by.role == "SUPERVISOR"
        and not reviewed_by.is_superuser
    ):
        try:
            reviewer_profile = StaffProfile.objects.get(
                user=reviewed_by
            )
        except StaffProfile.DoesNotExist:
            raise AttendanceError(
                "Your account is not linked to a staff profile."
            )

        if reviewer_profile.branch_id != override_request.branch_id:
            raise AttendanceError(
                "You can only review requests from your own branch."
            )

    old_status = override_request.status

    if decision == "APPROVE":
        new_status = AttendanceOverrideRequest.Status.APPROVED
        audit_action = "OVERRIDE_REQUEST_APPROVED"
    else:
        new_status = AttendanceOverrideRequest.Status.REJECTED
        audit_action = "OVERRIDE_REQUEST_REJECTED"

    now = timezone.now()

    override_request.status = new_status
    override_request.reviewed_by = reviewed_by
    override_request.reviewer_reason = reason
    override_request.reviewed_at = now

    override_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewer_reason",
            "reviewed_at",
        ]
    )

    AttendanceAuditLog.objects.create(
        attendance=override_request.attendance,
        shift_instance=override_request.shift_instance,
        action=audit_action,
        old_values={
            "status": old_status,
        },
        new_values={
            "status": new_status,
            "request_id": override_request.id,
            "reviewed_by_id": reviewed_by.id,
        },
        actor=reviewed_by,
        reason=reason,
    )

    return override_request


@transaction.atomic
def execute_attendance_override_request(
    *,
    executed_by,
    request_id,
):
    """
    Execute an approved assisted attendance request.

    Only the person who approved the request may execute it.
    The actual execution time is used as the attendance timestamp.
    Assisted actions are always marked as OVERRIDE, not GPS VERIFIED.
    """

    if not executed_by or not executed_by.is_authenticated:
        raise AttendanceError("Authentication is required.")

    allowed_roles = {"OWNER", "ADMIN", "SUPERVISOR"}

    if not (
        executed_by.is_superuser
        or executed_by.role in allowed_roles
    ):
        raise AttendanceError(
            "You are not authorized to execute assisted attendance."
        )

    try:
        override_request = (
            AttendanceOverrideRequest.objects
            .select_for_update(of=("self",))
            .get(pk=request_id)
        )
    except AttendanceOverrideRequest.DoesNotExist:
        raise AttendanceError(
            "Attendance override request does not exist."
        )

    if override_request.status != AttendanceOverrideRequest.Status.APPROVED:
        raise AttendanceError(
            "Only approved requests can be executed."
        )

    if not override_request.reviewed_by_id:
        raise AttendanceError(
            "This request has no recorded reviewer."
        )

    if override_request.reviewed_by_id != executed_by.id:
        raise AttendanceError(
            "Only the reviewer who approved this request can execute it."
        )

    try:
        staff = (
            StaffProfile.objects
            .select_for_update()
            .select_related("branch", "user")
            .get(pk=override_request.staff_id)
        )
    except StaffProfile.DoesNotExist:
        raise AttendanceError("Staff member does not exist.")

    if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
        raise AttendanceError(
            "Only active employees can receive assisted attendance."
        )

    if not staff.branch.is_active:
        raise AttendanceError("The employee's branch is inactive.")

    if staff.branch_id != override_request.branch_id:
        raise AttendanceError(
            "The employee's branch no longer matches the request."
        )

    try:
        shift_instance = (
            ShiftInstance.objects
            .select_for_update()
            .get(pk=override_request.shift_instance_id)
        )
    except ShiftInstance.DoesNotExist:
        raise AttendanceError("Shift instance does not exist.")

    if shift_instance.branch_id != staff.branch_id:
        raise AttendanceError(
            "The shift does not belong to the employee's branch."
        )

    if shift_instance.status == ShiftInstance.Status.FINALIZED:
        raise AttendanceError(
            "This shift has already been finalized."
        )

    now = timezone.now()

    # -------------------------------------------------
    # ASSISTED CLOCK-IN
    # -------------------------------------------------

    if override_request.action == AttendanceOverrideRequest.Action.CLOCK_IN:

        if override_request.attendance_id:
            raise AttendanceError(
                "This assisted clock-in request has already been executed."
            )

        if shift_instance.status == ShiftInstance.Status.COMPLETED:
            raise AttendanceError(
                "A completed shift cannot accept new clock-ins."
            )

        early_minutes = int(
            shift_instance.configuration_snapshot.get(
                "early_check_in_minutes",
                30,
            )
        )

        earliest_clock_in = (
            shift_instance.scheduled_start
            - timedelta(minutes=early_minutes)
        )

        if not earliest_clock_in <= now < shift_instance.scheduled_end:
            raise AttendanceError(
                "Assisted clock-in is outside the permitted shift window."
            )

        assignment = get_active_shift_assignment(
            staff,
            shift_instance.work_date,
        )

        authorization = None

        if assignment.shift != shift_instance.shift_type:
            authorization = (
                ShiftAttendanceAuthorization.objects
                .select_for_update(of=("self",))
                .filter(
                    staff=staff,
                    shift_instance=shift_instance,
                    permanent_shift_assignment=assignment,
                    status="APPROVED",
                )
                .first()
            )

            if not authorization or not authorization.reviewed_by_id:
                raise AttendanceError(
                    "The employee requires approved authorization "
                    "to work this different shift."
                )

        if AttendanceRecord.objects.filter(
            staff=staff,
            shift_instance=shift_instance,
        ).exists():
            raise AttendanceError(
                "Attendance has already been recorded for this shift."
            )

        grace_minutes = int(
            shift_instance.configuration_snapshot.get(
                "late_grace_minutes",
                15,
            )
        )

        late_deadline = (
            shift_instance.scheduled_start
            + timedelta(minutes=grace_minutes)
        )

        attendance_status = (
            AttendanceRecord.AttendanceStatus.LATE
            if now > late_deadline
            else AttendanceRecord.AttendanceStatus.ON_TIME
        )

        attendance = AttendanceRecord.objects.create(
            staff=staff,
            branch=staff.branch,
            shift_instance=shift_instance,
            shift_assignment=assignment,
            shift_authorization=authorization,
            attendance_status=attendance_status,
            checkout_status=AttendanceRecord.CheckoutStatus.OPEN,
            clock_in=now,
            clock_in_recorded_by=executed_by,
            clock_in_recorded_at=now,
            clock_in_assisted_reason=override_request.employee_reason,
            clock_in_latitude=override_request.latitude,
            clock_in_longitude=override_request.longitude,
            clock_in_accuracy=override_request.accuracy,
            clock_in_verification=AttendanceRecord.VerificationStatus.OVERRIDE,
        )

        if shift_instance.status == ShiftInstance.Status.SCHEDULED:
            old_status = shift_instance.status
            shift_instance.status = ShiftInstance.Status.IN_PROGRESS
            shift_instance.save(update_fields=["status"])

            AttendanceAuditLog.objects.create(
                attendance=attendance,
                shift_instance=shift_instance,
                action="SHIFT_STARTED",
                old_values={"status": old_status},
                new_values={"status": shift_instance.status},
                actor=executed_by,
                reason="Shift started through approved assisted clock-in.",
            )

        AttendanceAuditLog.objects.create(
            attendance=attendance,
            shift_instance=shift_instance,
            action="SUPERVISOR_ASSISTED_CLOCK_IN",
            old_values={},
            new_values={
                "attendance_id": attendance.id,
                "attendance_status": attendance.attendance_status,
                "checkout_status": attendance.checkout_status,
                "verification": attendance.clock_in_verification,
                "executed_by_id": executed_by.id,
                "request_id": override_request.id,
            },
            actor=executed_by,
            reason=override_request.employee_reason,
        )

        override_request.attendance = attendance
        override_request.save(update_fields=["attendance"])

        return attendance

    # -------------------------------------------------
    # ASSISTED CLOCK-OUT
    # -------------------------------------------------

    if override_request.action == AttendanceOverrideRequest.Action.CLOCK_OUT:

        if not override_request.attendance_id:
            raise AttendanceError(
                "This clock-out request has no linked attendance record."
            )

        try:
            attendance = (
                AttendanceRecord.objects
                .select_for_update(of=("self",))
                .get(pk=override_request.attendance_id)
            )
        except AttendanceRecord.DoesNotExist:
            raise AttendanceError(
                "The linked attendance record no longer exists."
            )

        if attendance.staff_id != staff.id:
            raise AttendanceError(
                "The attendance record belongs to another employee."
            )

        if attendance.shift_instance_id != shift_instance.id:
            raise AttendanceError(
                "The attendance record belongs to another shift."
            )

        if attendance.checkout_status != AttendanceRecord.CheckoutStatus.OPEN:
            raise AttendanceError(
                "This attendance record has already been checked out."
            )

        if not attendance.clock_in or now <= attendance.clock_in:
            raise AttendanceError(
                "Clock-out must happen after clock-in."
            )

        old_values = {
            "checkout_status": attendance.checkout_status,
            "clock_out": (
                attendance.clock_out.isoformat()
                if attendance.clock_out
                else None
            ),
        }

        attendance.clock_out = now
        attendance.checkout_status = AttendanceRecord.CheckoutStatus.MANUAL
        attendance.clock_out_recorded_by = executed_by
        attendance.clock_out_recorded_at = now
        attendance.clock_out_assisted_reason = override_request.employee_reason
        attendance.clock_out_latitude = override_request.latitude
        attendance.clock_out_longitude = override_request.longitude
        attendance.clock_out_accuracy = override_request.accuracy
        attendance.clock_out_verification = (
            AttendanceRecord.VerificationStatus.OVERRIDE
        )

        attendance.save(
            update_fields=[
                "clock_out",
                "checkout_status",
                "clock_out_recorded_by",
                "clock_out_recorded_at",
                "clock_out_assisted_reason",
                "clock_out_latitude",
                "clock_out_longitude",
                "clock_out_accuracy",
                "clock_out_verification",
                "updated_at",
            ]
        )

        AttendanceAuditLog.objects.create(
            attendance=attendance,
            shift_instance=shift_instance,
            action="SUPERVISOR_ASSISTED_CLOCK_OUT",
            old_values=old_values,
            new_values={
                "checkout_status": attendance.checkout_status,
                "clock_out": now.isoformat(),
                "verification": attendance.clock_out_verification,
                "executed_by_id": executed_by.id,
                "request_id": override_request.id,
            },
            actor=executed_by,
            reason=override_request.employee_reason,
        )

        return attendance

    raise AttendanceError("Unsupported attendance override action.")


