from rest_framework.permissions import BasePermission


class CustomerAccess(BasePermission):

    def has_permission(self, request, view):
        role = request.user.role

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return role in ['ADMIN', 'OWNER', 'SUPERVISOR', 'ACCOUNTS']

        return role in ['ADMIN', 'SUPERVISOR']


class VehicleAccess(BasePermission):

    def has_permission(self, request, view):
        role = request.user.role

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        if request.method == 'POST':
            return role in ['ADMIN', 'SUPERVISOR', 'DETAILER']

        if request.method in ('PUT', 'PATCH'):
            return role in ['ADMIN', 'SUPERVISOR']

        return False


class CreditAccountAccess(BasePermission):

    def has_permission(self, request, view):

        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return role in ['ADMIN', 'OWNER', 'ACCOUNTS']

        return role == 'ADMIN'

class CreditLedgerAccess(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role

        # View credit ledger and payment history.
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return role in ['ADMIN', 'OWNER', 'ACCOUNTS']

        # Only Admin and Accounts can record repayments.
        if request.method == 'POST':
            return role in ['ADMIN', 'ACCOUNTS']

        return False