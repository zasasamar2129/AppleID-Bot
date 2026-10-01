"""Shared rendering helpers for support tickets.

Used by both the admin panel and the user ticket view so a conversation reads
identically on both sides.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from app.database.models.enums import SupportStatus
from app.database.models.support import SupportMessage

# Telegram rejects messages over 4096 characters.
TELEGRAM_MAX_TEXT = 4096

STATUS_ICONS = {
    SupportStatus.OPEN: "🆕",
    SupportStatus.IN_PROGRESS: "⚡",
    SupportStatus.WAITING_USER: "👤",
    SupportStatus.RESOLVED: "✅",
    SupportStatus.CLOSED: "🚫",
}

CATEGORY_ICONS = {
    "payment": "💳",
    "order": "📦",
    "apple_id": "🍏",
    "wallet": "💰",
    "other": "❓",
}


def escape(text: str | None) -> str:
    """HTML-escape user-supplied text.

    The bot parses every message as HTML (see app/bot/bot.py), so a customer
    typing "<b>" or an unescaped "&" would otherwise break the render.
    """
    return html.escape(text or "", quote=False)


def truncate(text: str, limit: int) -> str:
    """Shorten to ``limit`` characters, adding an ellipsis when cut."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def relative_time(value: datetime | None) -> str:
    """Human-readable age of a timestamp, e.g. "2h ago"."""
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - value
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return value.strftime("%Y-%m-%d")


def ticket_title(status: SupportStatus, ticket_id: int) -> str:
    icon = STATUS_ICONS.get(status, "•")
    return f"{icon} #{ticket_id} · {status.value}"


def message_line(msg: SupportMessage, *, max_chars: int = 400) -> str:
    """One conversation line.

    ``SupportMessage`` has no ``sender`` relationship, so authorship is derived
    from which of the two nullable sender ids is set.
    """
    if msg.sender_admin_id is not None:
        prefix = "🛠 <b>Admin:</b> "
    else:
        prefix = "👤 <b>User:</b> "
    return f"{prefix}{escape(truncate(msg.message, max_chars))}"


def render_conversation(messages: list[SupportMessage], *, max_chars: int = 400) -> str:
    """Render a thread oldest-first, oldest messages dropped if too long.

    Keeps the newest messages (the actionable ones) when the full thread would
    exceed Telegram's limit.
    """
    if not messages:
        return "<i>(no messages yet)</i>"

    lines = [message_line(m, max_chars=max_chars) for m in messages]
    header = ""
    body = "\n\n".join(lines)
    while body and len(header + body) > TELEGRAM_MAX_TEXT:
        # Drop the oldest message and try again.
        lines.pop(0)
        if not lines:
            body = "<i>(conversation too long to display)</i>"
            break
        body = "\n\n".join(lines)
        header = "<i>… earlier messages omitted …</i>\n\n"
    return header + body
