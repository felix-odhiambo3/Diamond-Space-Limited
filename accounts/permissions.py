from rest_framework.permissions import BasePermission


class BaseRolePermission(BasePermission):

    allowed_roles = []

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return (
            user.is_superuser
            or user.role in self.allowed_roles
        )


class IsAdmin(BaseRolePermission):
    allowed_roles = ['ADMIN']


class IsOwner(BaseRolePermission):
    allowed_roles = ['OWNER']


class IsSupervisor(BaseRolePermission):
    allowed_roles = ['SUPERVISOR']


class IsAccounts(BaseRolePermission):
    allowed_roles = ['ACCOUNTS']


class IsCleaner(BaseRolePermission):
    allowed_roles = ['CLEANER']


class IsDetailer(BaseRolePermission):
    allowed_roles = ['DETAILER']


class IsOwnerOrSupervisor(BaseRolePermission):
    allowed_roles = ['OWNER', 'SUPERVISOR']


class IsOwnerOrAccounts(BaseRolePermission):
    allowed_roles = ['OWNER', 'ACCOUNTS']


class IsAdminOrOwner(BaseRolePermission):
    allowed_roles = ['ADMIN', 'OWNER']