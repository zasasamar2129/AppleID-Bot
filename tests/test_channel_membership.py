"""Tests for the mandatory channel-membership gate.

Pure unit tests (mock the Telegram API) — no DB / network needed. They
verify the membership-decision logic and fail-closed behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiogram.enums import ChatMemberStatus

from app.services.channel_membership_service import (
    ACCEPTED_STATUSES,
    ChannelMembershipService,
)


def _fake_member(status: str):
    return MagicMock(status=status)


class _FakeRedis:
    """Minimal async dict-like Redis stub."""

    def __init__(self):
        self.data: dict[str, bytes] = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value


@pytest.fixture
def service():
    bot = MagicMock()
    redis = _FakeRedis()
    svc = ChannelMembershipService(bot=bot, redis=redis)
    return svc


@pytest.mark.asyncio
async def test_member_allowed(service):
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.MEMBER))
    assert await service.is_member(123, require_fresh=True) is True


@pytest.mark.asyncio
async def test_administrator_allowed(service):
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.ADMINISTRATOR))
    assert await service.is_member(123, require_fresh=True) is True


@pytest.mark.asyncio
async def test_creator_allowed(service):
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.CREATOR))
    assert await service.is_member(123, require_fresh=True) is True


@pytest.mark.asyncio
async def test_left_denied(service):
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.LEFT))
    assert await service.is_member(123, require_fresh=True) is False


@pytest.mark.asyncio
async def test_kicked_denied(service):
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.KICKED))
    assert await service.is_member(123, require_fresh=True) is False


@pytest.mark.asyncio
async def test_restricted_denied(service):
    # restricted without guaranteed access -> fail closed (deny)
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.RESTRICTED))
    assert await service.is_member(123, require_fresh=True) is False


@pytest.mark.asyncio
async def test_api_timeout_fails_closed(service):
    service.bot.get_chat_member = AsyncMock(side_effect=TimeoutError("timed out"))
    assert await service.is_member(123, require_fresh=True) is False


@pytest.mark.asyncio
async def test_api_exception_fails_closed(service):
    from aiogram.exceptions import TelegramAPIError

    async def boom(*a, **k):
        raise TelegramAPIError("chat not found")

    service.bot.get_chat_member = boom
    assert await service.is_member(123, require_fresh=True) is False


@pytest.mark.asyncio
async def test_rejoin_restores_access(service):
    # First: not a member -> denied
    service.bot.get_chat_member = AsyncMock(return_value=_fake_member(ChatMemberStatus.LEFT))
    assert await service.is_member(123, require_fresh=True) is False
    # Then: joins -> allowed (fresh check bypasses any cached denial)
    service.bot.get_chat_member.return_value = _fake_member(ChatMemberStatus.MEMBER)
    assert await service.is_member(123, require_fresh=True) is True


def test_accepted_statuses_do_not_include_left_kicked():
    assert ChatMemberStatus.LEFT not in ACCEPTED_STATUSES
    assert ChatMemberStatus.KICKED not in ACCEPTED_STATUSES
    assert ChatMemberStatus.MEMBER in ACCEPTED_STATUSES


def test_localization_channel_keys_resolve():
    from app.localization import get_text

    for key in (
        "channel.access_required",
        "channel.join",
        "channel.check_membership",
        "channel.not_member",
        "channel.verified",
        "channel.verification_error",
    ):
        fa = get_text(key, "fa")
        en = get_text(key, "en")
        # Must resolve to the key itself (fallback) — i.e. no crash.
        assert isinstance(fa, str) and isinstance(en, str)
        # Channel username should appear in the access-required gate text.
        if key == "channel.access_required":
            assert "mobilemeisam2" in fa or "mobilemeisam2" in en


def test_no_unresolved_placeholders_in_channel_keys():
    from app.localization import get_text

    for key in (
        "channel.access_required",
        "channel.join",
        "channel.check_membership",
        "channel.not_member",
        "channel.verified",
        "channel.verification_error",
    ):
        fa = get_text(key, "fa")
        en = get_text(key, "en")
        for resolved in (fa, en):
            # Unresolved {placeholders} would remain as literal braces.
            assert "{" not in resolved and "}" not in resolved