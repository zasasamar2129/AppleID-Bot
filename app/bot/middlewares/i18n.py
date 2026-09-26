from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.config import settings
from app.localization import get_text


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        db_user = data.get("db_user")
        lang = db_user.language if db_user else settings.default_language
        data["lang"] = lang
        data["_"] = lambda key, **kwargs: get_text(key, lang, **kwargs)
        return await handler(event, data)
