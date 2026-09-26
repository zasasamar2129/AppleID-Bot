from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import button
from app.localization import get_text


def back_keyboard(back_callback: str, lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("common.back", lang), callback_data=back_callback, emoji_key="back", lang=lang))
    return kb.as_markup()


def cancel_keyboard(cancel_callback: str, lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("common.cancel", lang), callback_data=cancel_callback, style="danger", emoji_key="cancel", lang=lang))
    return kb.as_markup()


def confirm_cancel_keyboard(confirm_callback: str, cancel_callback: str, lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("products.confirm", lang), callback_data=confirm_callback, style="success", emoji_key="success", lang=lang))
    kb.add(button(get_text("common.cancel", lang), callback_data=cancel_callback, style="danger", emoji_key="cancel", lang=lang))
    return kb.as_markup()
