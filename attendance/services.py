
import math
from decimal import Decimal
from django.db import models

from django.db import transaction
from django.utils import timezone

from staff.models import StaffProfile, ShiftAssignment
from .models import AttendanceRecord


# Initial GPS configuration
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
    """
    Calculate the distance between two GPS coordinates
    using the Haversine formula.
    """

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
    """
    Verify that GPS coordinates are valid, sufficiently accurate,
    and within the branch's permitted attendance radius.
    """

    try:
        latitude = Decimal(str(latitude))
        longitude = Decimal(str(longitude))
        accuracy = Decimal(str(accuracy))
    except Exception:
        raise AttendanceError("Invalid GPS information.")

    if not latitude.is_finite() or not longitude.is_finite():
        raise AttendanceError("GPS coordinates must be finite numbers.")

    if not accuracy.is_finite():
        raise AttendanceError("GPS accuracy must be a finite number.")

    if not -90 <= latitude <= 90:
        raise AttendanceError("Invalid latitude.")

    if not -180 <= longitude <= 180:
        raise AttendanceError("Invalid longitude.")

    if accuracy <= 0:
        raise AttendanceError("GPS accuracy must be greater than zero.")

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
            f"You are outside the permitted attendance area. "
            f"Your distance is approximately {distance:.2f} metres."
        )

    return {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "distance": Decimal(str(round(distance, 2))),
    }


def get_active_shift_assignment(staff, work_date):
    """
    Find the employee's applicable shift assignment
    for the attendance work date.
    """

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
            "You do not have an active shift assignment for today."
        )

    return assignment


@transaction.atomic
def clock_in(
    *,
    user,
    latitude,
    longitude,
    accuracy,
    ip_address=None,
):
    """
    Clock in an employee after checking their account,
    branch, shift assignment and GPS location.
    """

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

    now = timezone.now()
    work_date = timezone.localdate(now)

    branch = staff.branch

    gps = validate_gps_location(
        branch=branch,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    shift_assignment = get_active_shift_assignment(
        staff,
        work_date,
    )

    existing_record = AttendanceRecord.objects.filter(
        staff=staff,
        work_date=work_date,
        shift_assignment=shift_assignment,
    ).first()

    if existing_record:
        if existing_record.status == AttendanceRecord.Status.OPEN:
            raise AttendanceError(
                "You are already clocked in."
            )

        raise AttendanceError(
            "You have already completed attendance for this shift."
        )

    record = AttendanceRecord.objects.create(
        staff=staff,
        branch=branch,
        shift_assignment=shift_assignment,
        work_date=work_date,
        status=AttendanceRecord.Status.OPEN,
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
    """
    Clock out an employee who has an open attendance record.

    This supports overnight shifts because it searches for
    the employee's open record rather than requiring today's date.
    """

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

    record = (
        AttendanceRecord.objects
        .select_for_update()
        .filter(
            staff=staff,
            status=AttendanceRecord.Status.OPEN,
        )
        .order_by("-clock_in")
        .first()
    )

    if not record:
        raise AttendanceError(
            "You do not have an open attendance record."
        )

    now = timezone.now()

    if now <= record.clock_in:
        raise AttendanceError(
            "Clock-out time must be later than clock-in time."
        )

    gps = validate_gps_location(
        branch=record.branch,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )

    record.clock_out = now
    record.status = AttendanceRecord.Status.COMPLETED

    record.clock_out_latitude = gps["latitude"]
    record.clock_out_longitude = gps["longitude"]
    record.clock_out_accuracy = gps["accuracy"]
    record.clock_out_distance = gps["distance"]

    record.clock_out_verification = (
        AttendanceRecord.VerificationStatus.VERIFIED
    )

    record.clock_out_ip_address = ip_address

    record.save()

    return record
