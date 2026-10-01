"""Block/unblock detection tests.

The bot never subscribed to ``my_chat_member``, so ``users.is_blocked`` was a flag
nothing ever set: blocked users still counted as reachable and were messaged on
every broadcast. Registering the handler alone is not enough — the update type must
also appear in what the bot asks Telegram for, or no events ever arrive.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Dispatcher
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Chat,
    ChatMemberBanned,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    User,
)

import app.database.session as dbs
import app.handlers.blocked_user as bu

PRIVATE_ID = 999
CHANNEL_ID = -1002143420264


def _member(user: User) -> ChatMemberMember:
    return ChatMemberMember(user=user, status=ChatMemberStatus.MEMBER)


def _event(chat: Chat, new, user: User, *, old=None) -> ChatMemberUpdated:
    return ChatMemberUpdated(
        chat=chat,
        from_user=user,
        date=datetime.datetime.now(),  # noqa: DTZ005 - aiogram accepts naive
        old_chat_member=old if old is not None else _member(user),
        new_chat_member=new,
    )


async def _run(event, *, currently_blocked: bool = False) -> list[bool]:
    """Drive the handler; return the values passed to set_blocked.

    ``currently_blocked`` models what the DB already holds, so the handler's
    "no change needed" short-circuit is exercised realistically.
    """
    calls: list[bool] = []
    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=MagicMock())
    fake_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.database.repositories.user_repo.UserRepository") as repo_cls,
        patch.object(dbs, "async_session", MagicMock(return_value=fake_session)),
        patch.object(bu, "redis_client") as redis,
    ):
        repo_cls.return_value.get_by_telegram_id = AsyncMock(
            return_value=MagicMock(id=1, is_blocked=currently_blocked)
        )
        repo_cls.return_value.set_blocked = AsyncMock(
            side_effect=lambda _id, blocked: calls.append(blocked)
        )
        redis.delete = AsyncMock()
        await bu.track_block_status(event)
    return calls


@pytest.mark.asyncio
async def test_user_blocking_bot_is_flagged():
    """member -> kicked means the user blocked the bot."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    event = _event(
        chat,
        ChatMemberBanned(
            user=user, until_date=0, when=datetime.datetime.now()  # noqa: DTZ005
        ),
        user,
    )
    assert await _run(event) == [True], "blocking must set is_blocked=True"


@pytest.mark.asyncio
async def test_user_leaving_bot_is_flagged():
    """member -> left means the user removed the bot."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    assert await _run(_event(chat, ChatMemberLeft(user=user), user)) == [True]


@pytest.mark.asyncio
async def test_unblocking_clears_the_flag():
    """Coming back must make the user reachable again.

    Transitions kicked -> member, and the DB must already hold is_blocked=True,
    otherwise the handler correctly treats the event as a no-op.
    """
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    kicked = ChatMemberBanned(
        user=user, until_date=0, when=datetime.datetime.now()  # noqa: DTZ005
    )
    event = _event(chat, _member(user), user, old=kicked)
    assert await _run(event, currently_blocked=True) == [False]


@pytest.mark.asyncio
async def test_redundant_event_writes_nothing():
    """A member -> member update must not churn the flag."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    assert await _run(_event(chat, _member(user), user)) == []


@pytest.mark.asyncio
async def test_channel_events_are_ignored():
    """The same event type fires for channels; reacting would corrupt the flag."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    channel = Chat(id=CHANNEL_ID, type="channel")
    assert await _run(_event(channel, ChatMemberLeft(user=user), user)) == []


@pytest.mark.asyncio
async def test_unknown_user_is_not_created():
    """Blocking before ever registering must not INSERT a phantom row."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    event = _event(chat, ChatMemberLeft(user=user), user)

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=MagicMock())
    fake_session.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("app.database.repositories.user_repo.UserRepository") as repo_cls,
        patch.object(dbs, "async_session", MagicMock(return_value=fake_session)),
        patch.object(bu, "redis_client"),
    ):
        repo_cls.return_value.get_by_telegram_id = AsyncMock(return_value=None)
        repo_cls.return_value.create = AsyncMock()
        await bu.track_block_status(event)
        repo_cls.return_value.create.assert_not_called()


@pytest.mark.asyncio
async def test_db_failure_does_not_raise():
    """Bookkeeping must never break the update loop."""
    user = User(id=PRIVATE_ID, is_bot=False, first_name="Ali")
    chat = Chat(id=PRIVATE_ID, type="private")
    event = _event(chat, ChatMemberLeft(user=user), user)

    with patch("app.database.repositories.user_repo.UserRepository") as repo_cls:
        repo_cls.side_effect = Exception("database is gone")
        await bu.track_block_status(event)  # must not raise


# --------------------------------------------------------------------------
# Wiring: an unrequested update type never arrives
# --------------------------------------------------------------------------
def test_my_chat_member_is_subscribed_via_getupdates():
    """Registering a handler is not enough — Telegram must be asked for the type."""
    from app.bot.dispatcher import register_all_routers, setup_middlewares

    dp = Dispatcher(storage=MemoryStorage())
    register_all_routers(dp)
    setup_middlewares(dp)
    assert "my_chat_member" in dp.resolve_used_update_types()


def test_membership_gate_runs_before_the_database():
    """The gate must precede DB work, or a DB outage silences new users."""
    from app.bot.dispatcher import setup_middlewares

    dp = Dispatcher(storage=MemoryStorage())
    setup_middlewares(dp)
    # Entries are (middleware, is_outer) pairs wrapped by aiogram.
    names = [
        (m.middleware.__name__ if hasattr(m, "middleware") else type(m).__name__)
        for m in dp.update.outer_middleware
    ]
    assert "ChannelMembershipMiddleware" in names
    assert "DatabaseMiddleware" in names and "UserMiddleware" in names
    assert names.index("ChannelMembershipMiddleware") < names.index("DatabaseMiddleware"), (
        f"membership gate must be outermost, got order: {names}"
    )
