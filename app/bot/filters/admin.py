from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.database.models.enums import AdminRole


class IsAdmin(BaseFilter):
    """A user in ADMIN_IDS is always an admin. Users added via the admin panel
    (stored in the admin_users table with an active status) also qualify."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return False
        if user_id in settings.admin_ids_list:
            return True
        # Fall back to the admin_users table (cached admins are bootstrapped on startup)
        try:
            from app.database.repositories.admin_repo import AdminRepository
            from app.database.session import async_session

            async with async_session() as session:
                repo = AdminRepository(session)
                admin = await repo.get_by_telegram_id(user_id)
                return bool(admin and admin.is_active)
        except Exception:
            return False


class IsSuperAdmin(BaseFilter):
    """Only the configured super admins (ADMIN_IDS env) or DB SUPER_ADMIN role."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return False
        if user_id in settings.admin_ids_list:
            return True
        try:
            from app.database.repositories.admin_repo import AdminRepository
            from app.database.session import async_session

            async with async_session() as session:
                repo = AdminRepository(session)
                admin = await repo.get_by_telegram_id(user_id)
                return bool(admin and admin.is_active and admin.role == AdminRole.SUPER_ADMIN)
        except Exception:
            return False
