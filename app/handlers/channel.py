from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.bot import bot, redis_client
from app.bot.keyboards.channel import membership_gate_keyboard, membership_gate_text
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.config import settings
from app.localization import get_text
from app.security.rate_limit import RateLimiter
from app.services.channel_membership_service import ChannelMembershipService
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()

# Short cooldown so the check button cannot spam Telegram API calls.
_membership_limiter = RateLimiter(redis_client, enabled=settings.rate_limit_enabled)
_CHECK_WINDOW_SECONDS = 2


@router.callback_query(F.data == "channel:check")
async def check_membership(callback: CallbackQuery, state: FSMContext, lang="fa"):
    user_id = callback.from_user.id

    if not await _membership_limiter.check(
        f"user:{user_id}:membership_check",
        limit=1,
        window_seconds=_CHECK_WINDOW_SECONDS,
    ):
        await callback.answer(get_text("channel.verification_error", lang), show_alert=True)
        return

    service = ChannelMembershipService(bot)
    # The check button always performs a fresh Telegram API verification.
    is_member = await service.is_member(user_id, require_fresh=True)

    if is_member:
        # Clear any suspended FSM and remove the gate, then welcome + main menu.
        await state.clear()
        await MessageCleanupService.close(callback.message.chat.id)
        await MessageCleanupService.cleanup_user_ui(callback.message.chat.id)
        await MessageCleanupService.show_screen(
            chat_id=callback.message.chat.id,
            text=get_text("start.welcome", lang, name=callback.from_user.first_name),
            reply_markup=main_menu_keyboard(lang),
        )
        await callback.answer()
        return

    # Not a member: keep showing the gate with a clear message.
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=(
            get_text("channel.not_member", lang) + "\n\n" +
            membership_gate_text(lang)
        ),
        reply_markup=membership_gate_keyboard(lang),
        force_new=True,
    )
    await callback.answer()