from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.localization import get_text
from app.services.unlock_service import IPHONE_SERIES_ORDER


def iphone_series_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    """Two-column series selection keyboard.

    [17 Series] [16 Series]
    [15 Series] [14 Series]
    [13 Series] [12 Series]
    [11 Series] [X and Older]
    """
    kb = InlineKeyboardBuilder()
    for internal in IPHONE_SERIES_ORDER:
        kb.button(
            text=get_text(f"unlock.series.{internal}", lang),
            callback_data=f"unlock:series:{internal}",
        )
    # 2 columns, 4 rows
    kb.adjust(2)
    return kb.as_markup()


def yes_no_keyboard(action_prefix: str, lang: str = "fa", include_close: bool = True) -> InlineKeyboardMarkup:
    """Two-column yes/no keyboard. action_prefix e.g. 'unlock:email_access'."""
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ {get_text('unlock.yes', lang)}", callback_data=f"{action_prefix}:yes")
    kb.button(text=f"❌ {get_text('unlock.no', lang)}", callback_data=f"{action_prefix}:no")
    kb.row()
    if include_close:
        kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="unlock:close")
        kb.adjust(2)
    return kb.as_markup()


def skip_keyboard(action: str, lang: str = "fa") -> InlineKeyboardMarkup:
    """Skip + close keyboard for optional fields (password, additional info)."""
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⏭ {get_text('unlock.skip', lang)}", callback_data=action)
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="unlock:close")
    kb.adjust(1)
    return kb.as_markup()