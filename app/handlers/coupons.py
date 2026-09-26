from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_keyboard
from app.database.repositories.coupon_repo import CouponRepository
from app.localization import get_text
from app.states.coupon import CouponStates
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def show_coupon_menu(message: Message, lang: str = "fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✏️ {get_text('coupon.enter', lang)}", callback_data="coupon:enter")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="coupon:close")
    kb.adjust(1)
    # Tracked so it is edited/cleaned on Back/Main.
    await MessageCleanupService.show_screen(message.chat.id, get_text("coupon.title", lang), reply_markup=kb.as_markup())


@router.callback_query(F.data == "menu:coupon")
async def menu_coupon(callback: CallbackQuery, lang="fa"):
    await show_coupon_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "coupon:enter")
async def coupon_enter(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.send_temporary(
        callback.message.chat.id,
        get_text("coupon.enter_prompt", lang),
        reply_markup=cancel_keyboard("menu:main", lang),
    )
    await state.set_state(CouponStates.ENTER_CODE)
    await callback.answer()


@router.message(CouponStates.ENTER_CODE, F.text)
async def coupon_verify(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    code = message.text.strip().upper()
    if not code:
        await message.answer(get_text("coupon.invalid", lang))
        return

    coupon_repo = CouponRepository(session)
    coupon = await coupon_repo.get_by_code(code)

    if not coupon or not coupon.is_active:
        await message.answer(get_text("coupon.invalid", lang))
        return

    now = datetime.utcnow()
    if coupon.start_date and now < coupon.start_date:
        await message.answer(get_text("coupon.not_started", lang))
        return
    if coupon.end_date and now > coupon.end_date:
        await message.answer(get_text("coupon.expired", lang))
        return
    if coupon.global_usage_limit and coupon.usage_count >= coupon.global_usage_limit:
        await message.answer(get_text("coupon.usage_limit", lang))
        return

    user_usage = await coupon_repo.get_user_usage_count(coupon.id, db_user.id)
    if user_usage >= coupon.per_user_limit:
        await message.answer(get_text("coupon.already_used", lang))
        return

    # Store coupon in state for later use during checkout
    await state.update_data(coupon_code=code, coupon_id=coupon.id)
    # Send validation result as a tracked PROMPT response, then clear.
    sent = await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("coupon.valid", lang, discount=f"{coupon.value}{'%' if coupon.type.value == 'percentage' else ''}"),
    )
    await state.clear()
    # Remove the temporary prompt + user's input message after a short delay is not
    # required here; they are cleaned up whenever the user returns to the main menu.
    return sent


@router.callback_query(F.data == "coupon:close")
async def coupon_close(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer(get_text("common.closed", lang))