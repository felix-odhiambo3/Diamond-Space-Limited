
from django.urls import path

from .views import (
    CustomerListCreateView,
    CustomerDetailView,
    VehicleListCreateView,
    VehicleDetailView,
    CreditAccountListCreateView,
    CreditAccountDetailView,
    CreditAccountApproveView,
    CreditAccountSuspendView,
    CreditAccountCloseView,
    CreditAccountLedgerView,
    CreditAccountPaymentView,
    CreditAccountAllocationsView,
)

urlpatterns = [
    # Customers
    path(
        'customers/',
        CustomerListCreateView.as_view(),
        name='customer_list_create'
    ),
    path(
        'customers/<int:pk>/',
        CustomerDetailView.as_view(),
        name='customer_detail'
    ),

    # Vehicles
    path(
        '',
        VehicleListCreateView.as_view(),
        name='vehicle_list_create'
    ),
    path(
        '<int:pk>/',
        VehicleDetailView.as_view(),
        name='vehicle_detail'
    ),

    # Credit accounts
    path(
        'credit-accounts/',
        CreditAccountListCreateView.as_view(),
        name='credit_account_list_create'
    ),
    path(
        'credit-accounts/<int:pk>/',
        CreditAccountDetailView.as_view(),
        name='credit_account_detail'
    ),
    path(
        'credit-accounts/<int:pk>/approve/',
        CreditAccountApproveView.as_view(),
        name='credit_account_approve'
    ),
    path(
        'credit-accounts/<int:pk>/suspend/',
        CreditAccountSuspendView.as_view(),
        name='credit_account_suspend'
    ),
    path(
        'credit-accounts/<int:pk>/close/',
        CreditAccountCloseView.as_view(),
        name='credit_account_close'
    ),
        # Credit ledger and repayments
    path(
        'credit-accounts/<int:pk>/ledger/',
        CreditAccountLedgerView.as_view(),
        name='credit_account_ledger'
    ),
    path(
        'credit-accounts/<int:pk>/payments/',
        CreditAccountPaymentView.as_view(),
        name='credit_account_payment'
    ),
    path(
        'credit-accounts/<int:pk>/allocations/',
        CreditAccountAllocationsView.as_view(),
        name='credit_account_allocations'
    ),
]
