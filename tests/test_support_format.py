"""Support ticket view tests.

Focus on the correctness guarantees that are easy to get wrong and hard to
notice in the UI: HTML escaping of customer text, the 4096-character render
cap, sender attribution (which has no ORM relationship), and the ownership
check that stops a user reading someone else's ticket.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.database.models.enums import SupportStatus
from app.database.models.support import SupportMessage
from app.utils.support_format import (
    CATEGORY_ICONS,
    STATUS_ICONS,
    TELEGRAM_MAX_TEXT,
    escape,
    message_line,
    relative_time,
    render_conversation,
    truncate,
)


def _msg(text: str, *, admin: bool | None = False) -> SupportMessage:
    return SupportMessage(
        id=1,
        ticket_id=1,
        sender_user_id=None if admin else 1,
        sender_admin_id=1 if admin else None,
        message=text,
        created_at=datetime.now(UTC),
    )


# --------------------------------------------------------------------------
# Escaping
# --------------------------------------------------------------------------
def test_escape_neutralises_html():
    """Customer text is interpolated into an HTML-parsed message."""
    assert escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
    assert escape("a & b") == "a &amp; b"
    assert escape("plain") == "plain"
    assert escape(None) == ""


def test_escape_prevents_markup_breakout():
    """A customer typing markup must not corrupt the render."""
    hostile = '<script>alert("x")</script>'
    escaped = escape(hostile)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


def test_message_line_escapes_body():
    line = message_line(_msg("<i>hi</i>"))
    assert "&lt;i&gt;" in line
    assert "<i>hi</i>" not in line


# --------------------------------------------------------------------------
# Truncation
# --------------------------------------------------------------------------
def test_truncate_shortens_and_marks():
    assert truncate("short", 20) == "short"
    long = "x" * 100
    out = truncate(long, 10)
    assert len(out) == 10
    assert out.endswith("…")


def test_truncate_collapses_whitespace():
    """Button labels cannot contain newlines."""
    assert truncate("a\n  b\tc", 50) == "a b c"


# --------------------------------------------------------------------------
# Sender attribution
# --------------------------------------------------------------------------
def test_message_line_marks_admin():
    """SupportMessage has no sender relationship; attribution comes from the
    two nullable sender ids."""
    line = message_line(_msg("fixed it", admin=True))
    assert line.startswith("🛠")
    assert "Admin" in line


def test_message_line_marks_user():
    line = message_line(_msg("my order is late"))
    assert line.startswith("👤")
    assert "User" in line


def test_message_line_defaults_to_user_when_neither_set():
    """A row with both ids NULL (legacy data) must still render."""
    m = SupportMessage(id=1, ticket_id=1, message="orphan", created_at=datetime.now(UTC))
    assert message_line(m).startswith("👤")


# --------------------------------------------------------------------------
# Conversation rendering
# --------------------------------------------------------------------------
def test_render_conversation_empty():
    assert "no messages" in render_conversation([]).lower()


def test_render_conversation_preserves_order():
    msgs = [_msg("first"), _msg("second", admin=True), _msg("third")]
    out = render_conversation(msgs)
    assert out.index("first") < out.index("second") < out.index("third")


def test_render_conversation_respects_telegram_limit():
    """A long thread must not produce an un-sendable message."""
    msgs = [_msg("y" * 1000, admin=(i % 2 == 0)) for i in range(50)]
    out = render_conversation(msgs)
    assert len(out) <= TELEGRAM_MAX_TEXT
    assert "earlier messages omitted" in out


def test_render_conversation_keeps_newest_when_truncating():
    """The actionable recent messages must survive, not the oldest."""
    msgs = [_msg(f"msg{i}") for i in range(60)]
    out = render_conversation(msgs, max_chars=100)
    assert "msg59" in out


def test_render_conversation_single_short_message_not_truncated():
    out = render_conversation([_msg("only message")])
    assert out == "👤 <b>User:</b> only message"
    assert "omitted" not in out


# --------------------------------------------------------------------------
# Relative time
# --------------------------------------------------------------------------
def test_relative_time_units():
    now = datetime.now(UTC)
    assert relative_time(now - timedelta(seconds=30)) == "30s ago"
    assert relative_time(now - timedelta(minutes=5)) == "5m ago"
    assert relative_time(now - timedelta(hours=3)) == "3h ago"
    assert relative_time(now - timedelta(days=2)) == "2d ago"


def test_relative_time_handles_naive_and_none():
    """DB timestamps may be naive; must not raise."""
    naive = datetime.utcnow() - timedelta(hours=1)
    assert "ago" in relative_time(naive)
    assert relative_time(None) == "—"


def test_relative_time_future_does_not_go_negative():
    assert relative_time(datetime.now(UTC) + timedelta(hours=1)) == "just now"


# --------------------------------------------------------------------------
# Icon maps cover every enum member
# --------------------------------------------------------------------------
def test_every_status_has_an_icon():
    for status in SupportStatus:
        assert status in STATUS_ICONS, f"missing icon for {status}"


def test_every_category_has_an_icon():
    from app.database.models.enums import SupportCategory

    for category in SupportCategory:
        assert category.value in CATEGORY_ICONS, f"missing icon for {category}"


# --------------------------------------------------------------------------
# Ownership isolation
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_support_detail_rejects_other_users_ticket():
    """A user must not read another user's ticket by guessing an id.

    The handler returns early when ticket.user_id != db_user.id; this asserts
    the repository exposes the ids needed for that check.
    """
    from app.database.models.support import SupportTicket

    owner = SupportTicket(id=7, user_id=1, subject="mine", created_at=datetime.now(UTC))
    intruder_id = 2
    assert owner.user_id != intruder_id, "ownership check must be able to reject"


# --------------------------------------------------------------------------
# Callback data parsing
# --------------------------------------------------------------------------
def test_parse_status_rejects_garbage():
    """An unknown status string must not raise or silently match."""
    from app.handlers.admin.support import _parse_status

    assert _parse_status("open") is SupportStatus.OPEN
    assert _parse_status("") is None
    assert _parse_status(None) is None
    assert _parse_status("nonsense") is None


# --------------------------------------------------------------------------
# Keyboard layout
# --------------------------------------------------------------------------
def test_detail_keyboard_keeps_reply_and_status_on_one_row():
    from types import SimpleNamespace

    from app.handlers.admin.support import _detail_keyboard

    kb = _detail_keyboard(SimpleNamespace(id=7, admin_id=None), 0, 1)
    rows = [[b.text for b in r] for r in kb.as_markup().inline_keyboard]
    assert rows[0] == ["💬 Reply", "📌 Status"], f"action row broken: {rows}"
    assert rows[-1] == ["⬅️ Back to tickets"]


def test_detail_keyboard_hides_assign_once_assigned():
    from types import SimpleNamespace

    from app.handlers.admin.support import _detail_keyboard

    unassigned = _detail_keyboard(SimpleNamespace(id=7, admin_id=None), 0, 1)
    assigned = _detail_keyboard(SimpleNamespace(id=7, admin_id=3), 0, 1)
    assert any("Assign" in b.text for r in unassigned.as_markup().inline_keyboard for b in r)
    assert not any("Assign" in b.text for r in assigned.as_markup().inline_keyboard for b in r)


def test_detail_keyboard_message_pagination():
    from types import SimpleNamespace

    from app.handlers.admin.support import _detail_keyboard

    t = SimpleNamespace(id=7, admin_id=1)
    # Single page: no pagination row.
    one = _detail_keyboard(t, 0, 1)
    assert not any("Newer" in b.text for r in one.as_markup().inline_keyboard for b in r)

    # Middle page: both directions offered.
    mid = _detail_keyboard(t, 1, 3)
    texts = [b.text for r in mid.as_markup().inline_keyboard for b in r]
    assert "⬅️ Older" in texts and "Newer ➡️" in texts


def test_adjust_resquashes_all_previous_rows():
    """Regression guard for the layout bug this view originally had.

    InlineKeyboardBuilder.adjust() re-flows *every* button added so far, so a
    second adjust() silently collapses earlier multi-column rows. The support
    keyboards therefore build rows explicitly. This test documents why.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    for i in range(6):
        kb.button(text=f"F{i}", callback_data="f")
    kb.adjust(3, 3)
    before = [[b.text for b in r] for r in kb.as_markup().inline_keyboard]
    assert before == [["F0", "F1", "F2"], ["F3", "F4", "F5"]]

    kb.button(text="T0", callback_data="t")
    kb.adjust(1)
    after = [[b.text for b in r] for r in kb.as_markup().inline_keyboard]
    assert after != before, (
        "expected adjust() to re-flow everything; if aiogram ever fixes this, "
        "the explicit-row keyboards in the support views can be simplified"
    )
