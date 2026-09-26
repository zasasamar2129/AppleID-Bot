from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from app.bot.bot import redis_client
from app.config import settings

logger = logging.getLogger(__name__)

# Telegram membership statuses that count as "in the channel".
ACCEPTED_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
}


class ChannelMembershipService:
    """Centralized membership verification against the required channel.

    Telegram is the source of truth. A short-TTL cache (default 60s) avoids
    hammering the Telegram API on every update; the ``require_fresh`` flag
    (used by the ✅ بررسی عضویت button) always bypasses the cache and performs
    a fresh ``get_chat_member`` call. On any Telegram API failure the check
    fails closed (denies access) so we never grant access we could not verify.
    """

    # How long a verified membership result may be cached (seconds).
    CACHE_TTL_SECONDS = 60

    def __init__(self, bot: Bot, redis=redis_client):
        self.bot = bot
        self.redis = redis

    async def is_member(self, user_id: int, require_fresh: bool = False) -> bool:
        """Return True only if Telegram reports an active membership status.

        Accepted: creator, administrator, member. Anything else (left,
        kicked, restricted-without-access) is denied. API exceptions fail
        closed and log at WARNING (no sensitive data).

        Set ``require_fresh=True`` (e.g. the check-membership button) to
        always re-query Telegram instead of trusting a cache entry.
        """
        cache_key = f"channel_membership:{settings.required_channel_id}:{user_id}"
        if not require_fresh:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached == b"1"
            except Exception:
                pass  # cache read failure -> fall through to real check

        result = await self._check_telegram(user_id)

        # Cache the result briefly (only cache definite answers, not failures).
        if result:
            try:
                await self.redis.set(cache_key, b"1", ex=self.CACHE_TTL_SECONDS)
            except Exception:
                pass
        return result

    async def _check_telegram(self, user_id: int) -> bool:
        try:
            member = await self.bot.get_chat_member(
                chat_id=settings.required_channel_id,
                user_id=user_id,
            )
            status = getattr(member, "status", None)
            return status in ACCEPTED_STATUSES
        except TelegramBadRequest as e:
            # e.g. user not found in chat, bot lacks access, channel invalid
            logger.warning(
                "Membership check failed (bad request) for user %s: %s",
                user_id,
                e.message,
            )
            return False
        except TelegramAPIError as e:
            logger.warning(
                "Membership check failed (API) for user %s: %s",
                user_id,
                e.message,
            )
            return False
        except Exception as e:  # noqa: BLE001 - network/timeout etc, fail closed
            logger.warning(
                "Membership check errored for user %s: %s",
                user_id,
                type(e).__name__,
            )
            return False

    async def is_admin(self, user_id: int) -> bool:
        """Cheap admin check: env ADMIN_IDS first, DB admin_users table fallback."""
        if user_id in settings.admin_ids_list:
            return True
        try:
            from app.database.repositories.admin_repo import AdminRepository
            from app.database.session import async_session

            async with async_session() as session:
                repo = AdminRepository(session)
                admin = await repo.get_by_telegram_id(user_id)
                return bool(admin and admin.is_active)
        except Exception:
            return False

    async def check_channel_access(self) -> bool:
        """Startup health check: verify the bot can query the channel.

        Returns False (without crashing the bot) when the channel is
        missing/inaccessible, logging a clear admin-facing warning.
        """
        try:
            me = await self.bot.get_me()
            await self.bot.get_chat_member(
                chat_id=settings.required_channel_id,
                user_id=me.id,
            )
            logger.info(
                "Channel membership check OK for chat %s", settings.required_channel_id
            )
            return True
        except Exception as e:  # noqa: BLE001 - never crash startup for config issues
            logger.warning(
                "Required channel %s is not accessible to the bot. "
                "Verify REQUIRED_CHANNEL_ID and that the bot is an admin/member "
                "of the channel. Error: %s",
                settings.required_channel_id,
                type(e).__name__,
            )
            return False