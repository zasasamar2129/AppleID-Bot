from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.admin import AdminUser
from app.database.models.enums import AdminRole


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, telegram_id: int, first_name: str, username: str | None = None, last_name: str | None = None, role: AdminRole = AdminRole.ADMIN, permissions: list[str] | None = None) -> AdminUser:
        admin = AdminUser(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            role=role,
            permissions=",".join(permissions) if permissions else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def get_by_telegram_id(self, telegram_id: int) -> AdminUser | None:
        stmt = select(AdminUser).where(AdminUser.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, admin_id: int) -> AdminUser | None:
        return await self.session.get(AdminUser, admin_id)

    async def update_role(self, admin_id: int, role: AdminRole) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.role = role
            admin.updated_at = datetime.utcnow()
            await self.session.commit()

    async def update_permissions(self, admin_id: int, permissions: list[str]) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.permissions = ",".join(permissions)
            admin.updated_at = datetime.utcnow()
            await self.session.commit()

    async def set_active(self, admin_id: int, active: bool) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.is_active = active
            admin.updated_at = datetime.utcnow()
            await self.session.commit()

    async def get_all(self) -> list[AdminUser]:
        stmt = select(AdminUser).order_by(AdminUser.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
