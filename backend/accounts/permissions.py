from rest_framework.permissions import BasePermission


def has_role(user, *roles):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=roles).exists()


class IsStoreManager(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, "Store Manager", "Admin")


class IsSupportStaff(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, "Support Agent", "Store Manager", "Admin")
