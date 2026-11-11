
from django.urls import path

from .views import (
    AttendanceOverrideListCreateView,
    AttendanceOverrideDetailView,
    AttendanceOverrideReviewView,
    AttendanceOverrideExecuteView,
    AttendanceOverrideAuditView,
    ShiftInstanceListView,
)

urlpatterns = [
    path(
        'shifts/',
        ShiftInstanceListView.as_view(),
        name='attendance_shift_list',
    ),

    path(
        'overrides/',
        AttendanceOverrideListCreateView.as_view(),
        name='attendance_override_list_create',
    ),

    path(
        'overrides/<int:pk>/',
        AttendanceOverrideDetailView.as_view(),
        name='attendance_override_detail',
    ),

    path(
        'overrides/<int:pk>/review/',
        AttendanceOverrideReviewView.as_view(),
        name='attendance_override_review',
    ),

    path(
        'overrides/<int:pk>/execute/',
        AttendanceOverrideExecuteView.as_view(),
        name='attendance_override_execute',
    ),

    path(
        'overrides/<int:pk>/audit/',
        AttendanceOverrideAuditView.as_view(),
        name='attendance_override_audit',
    ),
]
