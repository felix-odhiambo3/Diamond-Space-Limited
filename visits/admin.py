from django.contrib import admin
from .models import Visit, VisitService


class VisitServiceInline(admin.TabularInline):
    model = VisitService
    extra = 0
    readonly_fields = (
        'service_name',
        'service_code',
        'service_category',
        'original_price',
        'added_by',
        'added_at',
    )


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'vehicle',
        'branch',
        'checked_in_by',
        'status',
        'arrival_time',
    )

    list_filter = ('status', 'branch', 'arrival_time')

    search_fields = (
        'vehicle__registration_number',
        'checked_in_by__username',
    )

    readonly_fields = ('arrival_time', 'created_at', 'updated_at')

    inlines = [VisitServiceInline]


@admin.register(VisitService)
class VisitServiceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'visit',
        'service_name',
        'original_price',
        'is_removed',
        'added_at',
    )

    list_filter = ('service_category', 'is_removed')
    search_fields = ('service_name', 'visit__vehicle__registration_number')
    readonly_fields = ('added_at',)