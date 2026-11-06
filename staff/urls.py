from django.urls import path
from .views import StaffShiftChangeView

from .views import (
    StaffListCreateView,
    StaffDetailView,
    StaffShiftHistoryView,
)

urlpatterns = [
    path('', StaffListCreateView.as_view(), name='staff_list_create'),

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

]