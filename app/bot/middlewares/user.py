from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from app.database.repositories.user_repo import UserRepository


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: User | None = data.get("event_from_user")
        if aiogram_user:
            session = data["session"]
            repo = UserRepository(session)
            db_user = await repo.get_by_telegram_id(aiogram_user.id)
            # Auto-register users who interact without pressing /start first.
            if db_user is None:
                db_user = await repo.create(
                    telegram_id=aiogram_user.id,
                    first_name=aiogram_user.first_name or "",
                    username=aiogram_user.username,
                    last_name=aiogram_user.last_name,
                    language=data.get("lang", "fa"),
                )
                from app.database.repositories.wallet_repo import WalletRepository

                await WalletRepository(session).get_or_create(db_user.id)
            data["db_user"] = db_user
        return await handler(event, data)
