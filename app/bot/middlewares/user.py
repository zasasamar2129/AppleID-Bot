from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy.exc import SQLAlchemyError

from app.database.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Resolve (and if needed auto-register) the DB user for this update.

    Fail-soft by design: this middleware runs BEFORE the membership gate, so a
    database problem here previously killed the update before the user ever saw
    the "join the channel" prompt — total silence for brand-new users, whose
    first interaction triggers the INSERT.

    On failure we log and continue with ``db_user = None``. I18nMiddleware
    already falls back to the default language for a missing user, and the
    membership gate needs no DB row, so the user still gets a reply.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: User | None = data.get("event_from_user")
        if aiogram_user:
            data["db_user"] = await self._resolve(aiogram_user, data)
        return await handler(event, data)

    async def _resolve(self, aiogram_user: User, data: dict[str, Any]) -> Any:
        try:
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
            return db_user
        except SQLAlchemyError:
            logger.exception(
                "Database unavailable resolving user_id=%s; continuing without a "
                "DB record so the update is not lost",
                aiogram_user.id,
            )
        except Exception:
            logger.exception(
                "Unexpected error resolving user_id=%s; continuing without a DB record",
                aiogram_user.id,
            )
        return None
