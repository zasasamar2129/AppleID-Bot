from __future__ import annotations

import re
import unicodedata

from aiogram.types import InlineKeyboardButton

from app.config import settings
from app.localization.emoji import Emoji

# Chars that look like letters but are actually symbols/icons (e.g. U+2139 INFO).
_ICON_LIKE_LETTERS = {"ℹ"}  # ℹ


def _is_icon_char(ch: str) -> bool:
    """True when a single character is an emoji/symbol icon rather than a letter."""
    if ch in _ICON_LIKE_LETTERS:
        return True
    cat = unicodedata.category(ch)
    # Emoji, symbols, marks (variation selectors / skin tone), and format chars.
    if cat.startswith("S") or cat.startswith("M") or cat in ("Cf", "Cc", "Zs"):
        return True
    return False


def _strip_leading_emoji(text: str) -> str:
    """Remove the leading emoji/icon grapheme (and following spaces) from a label.

    "🛒 خرید Apple ID" -> "خرید Apple ID"
    "ℹ️ درباره ما"      -> "درباره ما"
    "کیف پول"           -> "کیف پول"  (unchanged)

    Stops as soon as it reaches a real letter/digit (Persian, Latin, etc.), so
    labels that start with plain text are never affected.
    """
    if not text:
        return text
    i = 0
    seen_icon = False
    while i < len(text) and _is_icon_char(text[i]):
        seen_icon = True
        i += 1
    if not seen_icon:
        return text
    while i < len(text) and text[i].isspace():
        i += 1
    return text[i:]


def get_custom_emoji_id(field_name: str) -> str | None:
    """Return a custom emoji ID from settings, honoring CUSTOM_EMOJI_ENABLED.

    Returns None when custom emoji are disabled or the ID is unset, so callers
    can always fall back to Unicode emoji.
    """
    if not getattr(settings, "custom_emoji_enabled", False):
        return None
    emoji_id = getattr(settings, field_name, None)
    return emoji_id or None


def button(
    text: str,
    callback_data: str | None = None,
    style: str | None = None,  # "primary", "success", "danger", None
    emoji_key: str | None = None,
    emoji_id: str | None = None,
    lang: str = "fa",
    url: str | None = None,
) -> InlineKeyboardButton:
    """Build an InlineKeyboardButton.

    - `emoji_key`: prefixes a Unicode emoji (from Emoji) as fallback icon.
    - `emoji_id`: sets ``icon_custom_emoji_id`` (custom animated emoji) and
      strips any leading Unicode emoji that emoji_key/base text would otherwise
      render, so only the custom emoji icon appears.
    """
    btn_text = text
    if emoji_key:
        unicode_emoji = getattr(Emoji, emoji_key.upper(), "")
        if unicode_emoji and not btn_text.startswith(unicode_emoji):
            btn_text = f"{unicode_emoji} {btn_text}"

    # When a custom emoji ID is present, remove the leading Unicode fallback.
    if emoji_id:
        btn_text = _strip_leading_emoji(btn_text)

    kwargs: dict = {"text": btn_text}
    if url:
        kwargs["url"] = url
    elif callback_data:
        kwargs["callback_data"] = callback_data
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if style:
        kwargs["style"] = style

    return InlineKeyboardButton(**kwargs)