
from django.contrib import admin

from .models import (
    ShiftConfiguration,
    ShiftInstance,
    ShiftAttendanceAuthorization,
    AttendanceRecord,
    AttendanceOverrideRequest,
    AttendanceAuditLog,
    ShiftReport,
)


@admin.register(ShiftConfiguration)
class ShiftConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "shift_type",
        "start_time",
        "end_time",
        "early_check_in_minutes",
        "late_grace_minutes",
        "is_active",
        "version",
    )
    list_filter = ("branch", "shift_type", "is_active")
    search_fields = ("branch__name", "branch__code")


@admin.register(ShiftInstance)
class ShiftInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "shift_type",
        "work_date",
        "scheduled_start",
        "scheduled_end",
        "status",
    )
    list_filter = ("branch", "shift_type", "status", "work_date")
    search_fields = ("branch__name", "branch__code")
    readonly_fields = ("configuration_snapshot",)


@admin.register(ShiftAttendanceAuthorization)
class ShiftAttendanceAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "staff",
        "shift_instance",
        "status",
        "requested_by",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status", "shift_instance__branch")
    search_fields = (
        "staff__staff_number",
        "staff__user__username",
    )
    readonly_fields = ("created_at",)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "staff",
        "branch",
        "shift_instance",
        "attendance_status",
        "checkout_status",
        "clock_in",
        "clock_out",
    )
    list_filter = (
        "attendance_status",
        "checkout_status",
        "branch",
        "shift_instance__shift_type",
    )
    search_fields = (
        "staff__staff_number",
        "staff__user__username",
        "staff__user__first_name",
        "staff__user__last_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(AttendanceOverrideRequest)
class AttendanceOverrideRequestAdmin(admin.ModelAdmin):
    list_display = (
        "staff",
        "branch",
        "action",
        "status",
        "created_at",
        "reviewed_by",
    )
    list_filter = ("status", "action", "branch")
    search_fields = (
        "staff__staff_number",
        "staff__user__username",
    )
    readonly_fields = ("created_at",)


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "attendance",
        "shift_instance",
        "actor",
        "created_at",
    )
    list_filter = ("action", "created_at")
    search_fields = (
        "actor__username",
        "reason",
    )
    readonly_fields = (
        "attendance",
        "shift_instance",
        "action",
        "old_values",
        "new_values",
        "actor",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ShiftReport)
class ShiftReportAdmin(admin.ModelAdmin):
    list_display = (
        "shift_instance",
        "generated_at",
        "finalized_at",
        "finalized_by",
    )
    readonly_fields = (
        "shift_instance",
        "report_data",
        "generated_at",
        "finalized_at",
        "finalized_by",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
