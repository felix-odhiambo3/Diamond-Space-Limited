from django.contrib import admin

from .models import (
    StaffProfile,
    ShiftAssignment,
    StaffStatusHistory,
)

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):

    list_display = (
        'staff_number',
        'user',
        'branch',
        'phone_number',
        'employment_status',
        'is_archived',
        'date_joined',
        'archived_at',
    )

    list_filter = (
        'branch',
        'employment_status',
        'is_archived',
    )

    search_fields = (
        'staff_number',
        'user__username',
        'user__email',
        'phone_number',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'archived_at',
        'archived_by',
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

@admin.register(StaffStatusHistory)
class StaffStatusHistoryAdmin(admin.ModelAdmin):

    list_display = (
        'staff',
        'action',
        'performed_by',
        'created_at',
    )

    list_filter = (
        'action',
        'created_at',
    )

    search_fields = (
        'staff__staff_number',
        'performed_by__username',
        'reason',
    )

    readonly_fields = (
        'staff',
        'action',
        'performed_by',
        'reason',
        'created_at',
    )