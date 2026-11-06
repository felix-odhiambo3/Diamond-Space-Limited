from django.db import transaction
from django.core.exceptions import ValidationError
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
    staff = StaffProfile.objects.select_for_update().get(
        pk=staff_id
    )

    if staff.employment_status != StaffProfile.EmploymentStatus.ACTIVE:
        raise ValidationError(
            "Only active staff members can receive shift assignments."
        )

    current_assignment = ShiftAssignment.objects.filter(
        staff=staff,
        effective_to__isnull=True
    ).order_by('-effective_from').first()

    if current_assignment:
        if effective_from <= current_assignment.effective_from:
            raise ValidationError(
                "A new assignment must start after the current assignment began."
            )

        current_assignment.effective_to = (
            effective_from - timezone.timedelta(days=1)
        )

        current_assignment.save(
            update_fields=['effective_to']
        )

    assignment = ShiftAssignment.objects.create(
        staff=staff,
        shift=shift,
        effective_from=effective_from,
        changed_by=changed_by,
        reason=reason
    )

    return assignment