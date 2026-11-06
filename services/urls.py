from django.urls import path

from .views import (
    ServiceListCreateView,
    ServiceDetailView,
)

urlpatterns = [
    path('', ServiceListCreateView.as_view(), name='service_list_create'),
    path('<int:pk>/', ServiceDetailView.as_view(), name='service_detail'),
]