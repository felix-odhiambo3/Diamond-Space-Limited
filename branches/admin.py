from django.contrib import admin
from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'code',
        'town',
        'phone',
        'is_active',
    )

    list_filter = ('is_active', 'town')

    search_fields = (
        'name',
        'code',
        'town',
        'phone',
    )

    ordering = ('name',)