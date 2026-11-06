from django.urls import path
from .views import VisitListCreateView, VisitDetailView
from .views import VisitServiceListCreateView
from .views import ServiceAssignmentListCreateView
from .views import (
    VisitListCreateView,
    VisitDetailView,
    VisitServiceListCreateView,
    ServiceAssignmentListCreateView,
    ServiceAssignmentRemoveView,
)

urlpatterns = [
    path('', VisitListCreateView.as_view(), name='visit_list_create'),
    path('<int:pk>/', VisitDetailView.as_view(), name='visit_detail'),
    path(
    '<int:visit_id>/services/',
    VisitServiceListCreateView.as_view(),
    name='visit_services'
),
path(
    '<int:visit_id>/services/<int:visit_service_id>/assignments/',
    ServiceAssignmentListCreateView.as_view(),
    name='service_assignments'
),
path(
    '<int:visit_id>/services/<int:visit_service_id>/assignments/<int:assignment_id>/remove/',
    ServiceAssignmentRemoveView.as_view(),
    name='remove_service_assignment'
),
]