from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.referral_repo import ReferralRepository
from app.localization import get_text

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:referrals")
async def admin_referrals_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    repo = ReferralRepository(session)
    total = await repo.count_all_referrals()
    text = (
        f"🎁 {get_text('admin.referrals', lang)}\n\n"
        f"{get_text('admin.referrals.total', lang, count=total)}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="admin:main")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()
