from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.localization import get_text


class Paginator:
    def __init__(self, items: list[Any], page_size: int = 5, callback_prefix: str = "page"):
        self.items = items
        self.page_size = page_size
        self.callback_prefix = callback_prefix
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)

    def get_page(self, page: int) -> list[Any]:
        start = (page - 1) * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def get_keyboard(self, current_page: int, lang: str = "fa") -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        if current_page > 1:
            kb.add(InlineKeyboardButton(text=get_text("pagination.prev", lang), callback_data=f"{self.callback_prefix}:{current_page-1}"))
        kb.add(InlineKeyboardButton(text=get_text("pagination.page", lang, current=current_page, total=self.total_pages), callback_data="noop"))
        if current_page < self.total_pages:
            kb.add(InlineKeyboardButton(text=get_text("pagination.next", lang), callback_data=f"{self.callback_prefix}:{current_page+1}"))
        kb.adjust(3)
        return kb.as_markup()
