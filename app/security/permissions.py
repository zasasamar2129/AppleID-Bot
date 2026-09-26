from __future__ import annotations

from enum import Enum

from app.database.models.enums import AdminRole


class Permission(str, Enum):
    MANAGE_USERS = "manage_users"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_ORDERS = "manage_orders"
    MANAGE_PAYMENTS = "manage_payments"
    MANAGE_WALLET = "manage_wallet"
    MANAGE_COUPONS = "manage_coupons"
    SEND_BROADCAST = "send_broadcast"
    MANAGE_SUPPORT = "manage_support"
    VIEW_STATISTICS = "view_statistics"
    MANAGE_ADMINS = "manage_admins"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SETTINGS = "manage_settings"


# Mapping of roles to default permissions
ROLE_PERMISSIONS: dict[AdminRole, set[Permission]] = {
    AdminRole.SUPER_ADMIN: set(Permission),
    AdminRole.ADMIN: {
        Permission.MANAGE_USERS,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
        Permission.MANAGE_PAYMENTS,
        Permission.MANAGE_WALLET,
        Permission.MANAGE_COUPONS,
        Permission.SEND_BROADCAST,
        Permission.MANAGE_SUPPORT,
        Permission.VIEW_STATISTICS,
    },
    AdminRole.INVENTORY_MANAGER: {
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_PRODUCTS,
    },
    AdminRole.FINANCE: {
        Permission.MANAGE_PAYMENTS,
        Permission.MANAGE_WALLET,
        Permission.MANAGE_ORDERS,
    },
    AdminRole.SUPPORT: {
        Permission.MANAGE_SUPPORT,
    },
}


class PermissionManager:
    @staticmethod
    def get_permissions(role: AdminRole, extra_permissions: list[str] | None = None) -> set[Permission]:
        perms = set(ROLE_PERMISSIONS.get(role, set()))
        if extra_permissions:
            for p in extra_permissions:
                try:
                    perms.add(Permission(p))
                except ValueError:
                    pass
        return perms

    @staticmethod
    def has_permission(role: AdminRole, permission: Permission, extra_permissions: list[str] | None = None) -> bool:
        return permission in PermissionManager.get_permissions(role, extra_permissions)
