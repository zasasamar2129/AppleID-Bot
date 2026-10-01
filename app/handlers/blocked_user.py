"""Detect users who block or leave the bot.

Telegram reports this via ``my_chat_member`` updates, which nothing in the project
handled. That left ``users.is_blocked`` as a flag nothing ever set, so blocked users
were still counted as reachable and messaged on every broadcast.

The flag matters beyond bookkeeping: it keeps the broadcast worker from repeatedly
hitting ``ForbiddenError`` for users who can never receive anything.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated

from app.bot.bot import redis_client
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

# Statuses that mean "this user can no longer receive our messages".
BLOCKED_STATUSES = {ChatMemberStatus.KICKED, ChatMemberStatus.LEFT}


@router.my_chat_member()
async def track_block_status(event: ChatMemberUpdated) -> None:
    """Keep ``users.is_blocked`` accurate when a user blocks or unblocks the bot."""
    chat = event.chat
    user = event.from_user

    # Only the bot's own private chat matters here. Channel membership changes
    # arrive on the same event type and would otherwise flip this flag wrongly.
    if chat.type != "private" or chat.id != user.id:
        return

    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    if new_status == old_status:
        return

    try:
        from app.database.repositories.user_repo import UserRepository
        from app.database.session import async_session

        blocked = new_status in BLOCKED_STATUSES

        async with async_session() as session:
            repo = UserRepository(session)
            db_user = await repo.get_by_telegram_id(user.id)
            if db_user is None:
                # Blocked before ever registering; nothing to flag yet.
                logger.debug(
                    "user_id=%s changed status %s -> %s but has no DB record",
                    user.id,
                    old_status,
                    new_status,
                )
                return
            if db_user.is_blocked == blocked:
                return
            await repo.set_blocked(db_user.id, blocked)

        logger.info(
            "user_id=%s %s the bot (status %s -> %s)",
            user.id,
            "blocked" if blocked else "unblocked",
            old_status,
            new_status,
        )

        if not blocked:
            # Drop the cached membership verdict so the next check is fresh
            # rather than reusing a decision made before the user came back.
            cache_key = f"channel_membership:{settings.required_channel_id}:{user.id}"
            try:
                await redis_client.delete(cache_key)
            except Exception:
                logger.debug("Could not clear membership cache for %s", user.id)
    except Exception:
        # Never let bookkeeping break the update loop.
        logger.exception("Failed to record block status for user_id=%s", user.id)
