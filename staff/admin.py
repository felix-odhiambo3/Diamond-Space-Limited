from django.contrib import admin
from .models import StaffProfile, ShiftAssignment


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):

    list_display = (
        'staff_number',
        'user',
        'branch',
        'phone_number',
        'employment_status',
        'date_joined',
    )

    list_filter = (
        'branch',
        'employment_status',
    )

    search_fields = (
        'staff_number',
        'user__username',
        'user__email',
        'phone_number',
    )


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):

    list_display = (
        'staff',
        'shift',
        'effective_from',
        'effective_to',
        'changed_by',
    )

    list_filter = ('shift', 'effective_from')
    search_fields = ('staff__staff_number',)