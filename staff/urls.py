
from django.urls import path

from .views import (
    StaffListCreateView,
    StaffDetailView,
    StaffShiftHistoryView,
    StaffShiftChangeView,
    StaffStatusActionView,
    StaffStatusHistoryView,
    StaffSelfProfileView,
    StaffBranchPickerView,
)


urlpatterns = [
    path(
        'me/',
        StaffSelfProfileView.as_view(),
        name='staff_self_profile'
    ),

    path(
        'branch-picker/',
        StaffBranchPickerView.as_view(),
        name='staff_branch_picker'
    ),

    path(
        '',
        StaffListCreateView.as_view(),
        name='staff_list_create'
    ),

    path(
        '<int:pk>/',
        StaffDetailView.as_view(),
        name='staff_detail'
    ),

    path(
        '<int:staff_id>/shifts/',
        StaffShiftHistoryView.as_view(),
        name='staff_shift_history'
    ),

    path(
        '<int:staff_id>/shifts/change/',
        StaffShiftChangeView.as_view(),
        name='staff_shift_change'
    ),

    path(
        '<int:staff_id>/status/',
        StaffStatusActionView.as_view(),
        name='staff_status_action'
    ),

    path(
        '<int:staff_id>/status-history/',
        StaffStatusHistoryView.as_view(),
        name='staff_status_history'
    ),
]
