from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.localization import get_text
from app.services.referral_service import ReferralService
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def show_referral_info(message: Message, session: AsyncSession, db_user, lang: str = "fa"):
    referral_service = ReferralService(session)
    link = await referral_service.generate_referral_link(db_user.id)
    count = await referral_service.get_referral_count(db_user.id)
    text = f"{get_text('referral.title', lang)}\n{get_text('referral.link', lang, link=link)}\n{get_text('referral.count', lang, count=count)}"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="referral:close")
    kb.adjust(1)

    # Tracked via MessageCleanupService so it is edited/cleaned on Back/Main.
    await MessageCleanupService.show_screen(message.chat.id, text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "referral:show")
async def referral_callback(callback: CallbackQuery, session, db_user, lang="fa"):
    await show_referral_info(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "referral:close")
async def referral_close(callback: CallbackQuery, lang="fa"):
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer(get_text("common.closed", lang))