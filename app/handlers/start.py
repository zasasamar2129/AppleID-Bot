from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.localization import get_text
from app.services.user_service import UserService
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session, db_user=None, lang="fa"):
    # Try to delete the /start command if possible
    try:
        await message.delete()
    except Exception:
        pass

    # Cleanup old UI messages before showing new main menu
    await MessageCleanupService.cleanup_user_ui(message.chat.id)

    # Process referral
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
        except ValueError:
            referrer_id = None

    user_service = UserService(session)
    user = await user_service.register_user(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username,
        last_name=message.from_user.last_name,
        language=lang,
        referrer_id=referrer_id,
    )

    await state.clear()
    welcome_text = get_text("start.welcome", lang, name=message.from_user.first_name)
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=welcome_text,
        reply_markup=main_menu_keyboard(lang),
    )


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    # Close current UI (deletes the tracked UI message)
    await MessageCleanupService.close(callback.message.chat.id)

    # Remove any temporary/prompt messages left over from FSM flows (coupons,
    # support, wallet prompts) while keeping protected business messages intact.
    await MessageCleanupService.cleanup_user_ui(callback.message.chat.id)

    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("start.welcome", lang, name=callback.from_user.first_name),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, lang="fa"):
    """Global cancel: clear FSM, clean temporary UI, return to main menu."""
    await state.clear()
    # Delete the /cancel command message before cleanup
    try:
        await message.delete()
    except Exception:
        pass
    await MessageCleanupService.cleanup_user_ui(message.chat.id)
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=get_text("common.cancelled", lang),
        reply_markup=main_menu_keyboard(lang),
    )
