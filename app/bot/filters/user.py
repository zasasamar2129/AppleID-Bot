from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.database.models.user import User


class IsBlocked(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, db_user: User | None) -> bool:
        return db_user is not None and db_user.is_blocked
