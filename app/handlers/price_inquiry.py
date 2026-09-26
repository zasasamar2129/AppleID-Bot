from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.localization import get_text
from app.services.price_inquiry_service import PriceInquiryService
from app.utils.formatting import format_price
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "menu:price_inquiry")
async def price_inquiry_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    service = PriceInquiryService(session)
    items = await service.get_active_items()
    if not items:
        text = f"🔎 {get_text('price_inquiry.title', lang)}\n\n{get_text('price_inquiry.empty', lang)}"
    else:
        text = f"🔎 {get_text('price_inquiry.title', lang)}\n\n"
        for item in items:
            name = item.name_fa if lang == "fa" else item.name_en
            price_str = format_price(item.price, lang)
            text += f"🍏 {name}\n💰 {price_str}\n\n"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="price_inquiry:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data == "price_inquiry:close")
async def price_inquiry_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer("Closed")
