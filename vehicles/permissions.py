
from rest_framework.permissions import BasePermission


class CustomerAccess(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return role in [
                'ADMIN',
                'OWNER',
                'SUPERVISOR',
                'ACCOUNTS',
            ]

        return role in ['ADMIN', 'SUPERVISOR']


class VehicleAccess(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        if request.method == 'POST':
            return role in [
                'ADMIN',
                'SUPERVISOR',
                'DETAILER',
            ]

        if request.method in ('PUT', 'PATCH'):
            return role in ['ADMIN', 'SUPERVISOR']

        return False


class VehicleCategoryAccess(BasePermission):
    """
    Authenticated users may view and select existing categories.

    Only ADMIN and SUPERVISOR may create new categories.
    OWNER is deliberately not included in category creation.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        if request.method == 'POST':
            return request.user.role in [
                'ADMIN',
                'SUPERVISOR',
            ]

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

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return role in ['ADMIN', 'OWNER', 'ACCOUNTS']

        if request.method == 'POST':
            return role in ['ADMIN', 'ACCOUNTS']

        return False
