"""Channel membership gate regression tests.

The bug these lock down: when the membership check or the gate render raised, the
outer middleware propagated the exception, the handler was skipped, and the user
received *nothing at all*. For a bot whose entire purpose at that moment is to ask
a non-member to join a channel, silence is the worst possible failure — the user
cannot tell it apart from being blocked, and it is nearly invisible in the logs.

The invariant under test: **a non-member always receives a reply**, and a failure to
verify never escalates to access (it fails closed).
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

import app.bot.middlewares.membership as mw
import app.utils.message_manager as mmmod


def _make_message(user_id: int = 555) -> tuple[Message, User]:
    user = User(id=user_id, is_bot=False, first_name="Ali")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=1,
        date=datetime.datetime.now(),  # noqa: DTZ005 - aiogram accepts naive
        chat=chat,
        from_user=user,
        text="/start",
    )
    return msg, user


def _make_callback(user_id: int = 555) -> tuple[CallbackQuery, User]:
    user = User(id=user_id, is_bot=False, first_name="Ali")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=1,
        date=datetime.datetime.now(),  # noqa: DTZ005
        chat=chat,
        from_user=user,
        text="gate",
    )
    cb = CallbackQuery(
        id="1", from_user=user, chat_instance="ci", data="something:else", message=msg
    )
    return cb, user


async def _run(
    event,
    user,
    *,
    is_admin=False,
    is_member=False,
    member_error=None,
    show_screen_error=None,
):
    """Drive the middleware; return (delivered_texts, handler_calls, callback_answered)."""
    sent: list[str] = []

    async def fake_send(chat_id=None, text=None, **kwargs):
        sent.append(str(text))
        return type("M", (), {"message_id": 1})()

    middleware = mw.ChannelMembershipMiddleware()
    middleware.service.is_admin = AsyncMock(return_value=is_admin)
    middleware.service.is_member = AsyncMock(
        side_effect=member_error, return_value=is_member
    )
    handler = AsyncMock()
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock(side_effect=fake_send)

    # CallbackQuery.answer is a bound TelegramMethod; swap in a recorder so we
    # can assert the button gets acknowledged instead of spinning forever.
    answered = []
    if isinstance(event, CallbackQuery):
        object.__setattr__(
            event,
            "answer",
            AsyncMock(side_effect=lambda *a, **k: answered.append(1)),
        )

    with (
        patch.object(mmmod, "bot", fake_bot),
        patch.object(mw, "bot", fake_bot),
        patch.object(
            mmmod.MessageCleanupService,
            "show_screen",
            AsyncMock(side_effect=show_screen_error),
        ),
    ):
        await middleware(handler, event, {"event_from_user": user, "lang": "en"})
    return sent, handler.await_count, len(answered)


# --------------------------------------------------------------------------
# The regression: failure must not mean silence
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_is_member_failure_still_replies():
    """A raising membership check must not swallow the update."""
    msg, user = _make_message()
    sent, handler_calls, _ = await _run(msg, user, member_error=Exception("redis down"))
    assert sent, "user received nothing when the membership check failed"
    assert "Access Restricted" in sent[0]
    assert handler_calls == 0, "must still fail closed (block the handler)"


@pytest.mark.asyncio
async def test_gate_render_failure_still_replies():
    """A failing show_screen must fall back to a direct send."""
    msg, user = _make_message()
    sent, handler_calls, _ = await _run(
        msg, user, is_member=False, show_screen_error=Exception("send failed")
    )
    assert sent, "user received nothing when the gate render failed"
    assert handler_calls == 0


@pytest.mark.asyncio
async def test_both_failing_still_replies():
    """Worst case: every dependency is broken. The user must still hear something."""
    msg, user = _make_message()
    sent, _, _ = await _run(
        msg,
        user,
        member_error=Exception("redis down"),
        show_screen_error=Exception("send failed"),
    )
    assert sent, "total silence when every dependency failed"
    assert "Access Restricted" in sent[0]


@pytest.mark.asyncio
async def test_callback_query_failure_still_answers():
    """A broken check on a button press must not leave the button spinning.

    Either the gate is re-sent or the callback is acknowledged — the user must
    get feedback and the button must stop spinning.
    """
    cb, user = _make_callback()
    sent, handler_calls, answered = await _run(
        cb, user, member_error=Exception("redis down")
    )
    assert handler_calls == 0, "non-member must not reach the handler"
    assert sent or answered == 1, (
        "callback press produced neither a message nor a callback answer"
    )


# --------------------------------------------------------------------------
# Normal behaviour must be unchanged
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_member_passes_through_to_handler():
    msg, user = _make_message()
    sent, handler_calls, _ = await _run(msg, user, is_member=True)
    assert handler_calls == 1, "a member must reach the handler"
    assert not sent, "a member must not be shown the gate"


@pytest.mark.asyncio
async def test_admin_bypasses_gate():
    msg, user = _make_message()
    sent, handler_calls, _ = await _run(msg, user, is_admin=True)
    assert handler_calls == 1
    assert not sent


@pytest.mark.asyncio
async def test_non_member_is_blocked():
    """Healthy non-member: handler skipped, gate requested."""
    msg, user = _make_message()
    _, handler_calls, _ = await _run(msg, user, is_member=False)
    assert handler_calls == 0, "non-member must not reach the handler"


@pytest.mark.asyncio
async def test_non_user_event_passes_through():
    """Chat-member updates etc. have no event_from_user and are not gated."""

    async def handler(event, data):
        return "passed"

    middleware = mw.ChannelMembershipMiddleware()
    result = await middleware(handler, object(), {})
    assert result == "passed"


# --------------------------------------------------------------------------
# The gate payload itself must not depend on Redis/DB
# --------------------------------------------------------------------------
def test_gate_text_needs_no_infrastructure():
    """The emergency fallback relies on these being pure functions."""
    from app.bot.keyboards.channel import membership_gate_keyboard, membership_gate_text

    text = membership_gate_text("en")
    assert "Access Restricted" in text
    kb = membership_gate_keyboard("en")
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert any(b.url for b in buttons), "must offer the join link"
    assert any(b.callback_data == "channel:check" for b in buttons), "must offer re-check"


def test_gate_text_is_html_safe():
    """Gate text is sent with parse_mode=HTML; markup would break the render."""
    from app.bot.keyboards.channel import membership_gate_text

    for lang in ("en", "fa"):
        text = membership_gate_text(lang)
        assert "<" not in text and ">" not in text, f"{lang} gate text contains markup"
        assert "&" not in text, f"{lang} gate text contains a bare ampersand"
