from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import button
from app.localization import get_text


def product_type_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("products.personal", lang), callback_data="purchase:type:personal", style="primary", emoji_key="user", lang=lang))
    kb.add(button(get_text("products.ready_made", lang), callback_data="purchase:type:ready_made", style="primary", emoji_key="instant", lang=lang))
    kb.add(button(get_text("common.back", lang), callback_data="menu:main", emoji_key="back", lang=lang))
    kb.adjust(1)
    return kb.as_markup()
