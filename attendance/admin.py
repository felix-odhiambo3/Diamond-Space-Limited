
from django.contrib import admin
from .models import AttendanceRecord, AttendanceOverrideRequest


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'staff',
        'branch',
        'work_date',
        'clock_in',
        'clock_out',
        'status',
        'clock_in_verification',
    )

    list_filter = (
        'status',
        'branch',
        'work_date',
        'clock_in_verification',
    )

    search_fields = (
        'staff__staff_number',
        'staff__user__username',
        'staff__user__first_name',
        'staff__user__last_name',
    )


@admin.register(AttendanceOverrideRequest)
class AttendanceOverrideRequestAdmin(admin.ModelAdmin):
    list_display = (
        'staff',
        'branch',
        'action',
        'status',
        'created_at',
        'reviewed_by',
    )

    list_filter = (
        'status',
        'action',
        'branch',
    )

    search_fields = (
        'staff__staff_number',
        'staff__user__username',
    )
