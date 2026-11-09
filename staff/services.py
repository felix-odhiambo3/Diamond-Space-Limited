
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import StaffProfile, ShiftAssignment


@transaction.atomic
def assign_staff_shift(
    staff_id,
    shift,
    effective_from,
    changed_by,
    reason=''
):
    if shift not in ShiftAssignment.Shift.values:
        raise ValidationError("Invalid shift assignment.")

    if effective_from < timezone.localdate():
        raise ValidationError(
            "Shift changes cannot be backdated."
        )

    staff = StaffProfile.objects.select_for_update().get(
        pk=staff_id
    )

    if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
        raise ValidationError(
            "Only active staff members can receive shift assignments."
        )

    open_assignments = ShiftAssignment.objects.filter(
        staff=staff,
        effective_to__isnull=True
    ).order_by('-effective_from')

    if open_assignments.count() > 1:
        raise ValidationError(
            "Multiple open-ended shift assignments exist. "
            "Resolve the conflicting records first."
        )

    current_assignment = open_assignments.first()

    if current_assignment:
        if effective_from <= current_assignment.effective_from:
            raise ValidationError(
                "A new assignment must start after the current assignment began."
            )

    overlapping_assignments = ShiftAssignment.objects.filter(
        staff=staff
    ).filter(
        models.Q(effective_to__isnull=True)
        | models.Q(effective_to__gte=effective_from)
    )

    if current_assignment:
        overlapping_assignments = overlapping_assignments.exclude(
            pk=current_assignment.pk
        )

    if overlapping_assignments.exists():
        raise ValidationError(
            "The new assignment would overlap an existing shift assignment."
        )

    if current_assignment:
        current_assignment.effective_to = (
            effective_from - timezone.timedelta(days=1)
        )
        current_assignment.save(
            update_fields=['effective_to']
        )

    return ShiftAssignment.objects.create(
        staff=staff,
        shift=shift,
        effective_from=effective_from,
        changed_by=changed_by,
        reason=reason
    )
