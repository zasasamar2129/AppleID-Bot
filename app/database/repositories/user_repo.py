from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, telegram_id: int, first_name: str, username: str | None = None, last_name: str | None = None, language: str = "fa") -> User:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language=language,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def update_last_active(self, telegram_id: int) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(last_active_at=datetime.utcnow(), updated_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_language(self, telegram_id: int, language: str) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(language=language, updated_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def set_blocked(self, user_id: int, blocked: bool) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.is_blocked = blocked
            user.updated_at = datetime.utcnow()
            await self.session.commit()

    async def set_vip(self, user_id: int, vip: bool) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.is_vip = vip
            user.updated_at = datetime.utcnow()
            await self.session.commit()

    async def update_referrer(self, user_id: int, referrer_id: int) -> None:
        user = await self.get_by_id(user_id)
        if user and not user.referrer_id:
            user.referrer_id = referrer_id
            user.updated_at = datetime.utcnow()
            await self.session.commit()

    async def count(self, active_only: bool = False) -> int:
        stmt = select(User)
        if active_only:
            stmt = stmt.where(User.is_blocked == False)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, query: str) -> list[User]:
        stmt = select(User).where(
            (User.username.ilike(f"%{query}%")) |
            (User.first_name.ilike(f"%{query}%")) |
            (User.last_name.ilike(f"%{query}%")) |
            (User.telegram_id == query if query.isdigit() else False)
        ).limit(50)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_profile(self, user_id: int, first_name: str, last_name: str | None = None, phone: str | None = None) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            user.updated_at = datetime.utcnow()
            await self.session.commit()
