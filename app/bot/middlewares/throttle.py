from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.bot import redis_client
from app.config import settings
from app.security.rate_limit import RateLimiter


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        self.limiter = RateLimiter(redis_client, enabled=settings.rate_limit_enabled)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = data.get("event_from_user").id if data.get("event_from_user") else None
        if user_id:
            # General rate limit: 10 messages per 5 seconds
            if not await self.limiter.check(f"user:{user_id}:general", limit=10, window_seconds=5):
                if isinstance(event, Message):
                    await event.answer("Too many requests. Please wait.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Too many requests. Please wait.", show_alert=True)
                return
        return await handler(event, data)
