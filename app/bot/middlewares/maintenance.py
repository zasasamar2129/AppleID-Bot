from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.localization import get_text


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if settings.maintenance_mode:
            # Allow admins
            db_user = data.get("db_user")
            if db_user and db_user.telegram_id in settings.admin_ids_list:
                return await handler(event, data)
            # Block others
            lang = data.get("lang", settings.default_language)
            if isinstance(event, Message):
                await event.answer(get_text("errors.maintenance", lang))
            elif isinstance(event, CallbackQuery):
                await event.answer(get_text("errors.maintenance", lang), show_alert=True)
            return
        return await handler(event, data)
