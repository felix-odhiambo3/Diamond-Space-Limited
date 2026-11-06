from django.urls import path
from .views import BranchListCreateView, BranchDetailView


urlpatterns = [
    path('', BranchListCreateView.as_view(), name='branch_list_create'),
    path('<int:pk>/', BranchDetailView.as_view(), name='branch_detail'),
]