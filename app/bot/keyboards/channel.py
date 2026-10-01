from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import button
from app.config import settings
from app.localization import get_text


def membership_gate_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    """Keyboard for the mandatory channel-membership gate.

    - A URL button to the required channel.
    - A callback button that performs a fresh membership check.
    """
    kb = InlineKeyboardBuilder()
    kb.add(button(
        get_text("channel.join", lang),
        url=settings.required_channel_url,
        lang=lang,
    ))
    kb.add(button(
        get_text("channel.check_membership", lang),
        callback_data="channel:check",
        style="success",
        lang=lang,
    ))
    kb.adjust(1)
    return kb.as_markup()


def membership_gate_text(lang: str = "fa") -> str:
    return get_text("channel.access_required", lang)