from rest_framework import permissions
from apps.accounts.models import UserRole

class IsAdminRole(permissions.BasePermission):
    """Allows access only to Super Admins."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == UserRole.ADMIN or request.user.is_superuser))


class IsOwnerRole(permissions.BasePermission):
    """Allows access only to Hall Owners."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.OWNER)


class IsCustomerRole(permissions.BasePermission):
    """Allows access only to registered Customers."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.CUSTOMER)


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role in [UserRole.OWNER, UserRole.ADMIN] or request.user.is_superuser))
