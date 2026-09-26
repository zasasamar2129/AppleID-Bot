from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.database.repositories.user_repo import UserRepository
from app.localization import get_text
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def show_language_menu(message: Message, lang: str = "fa"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang:fa")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
    ])
    await MessageCleanupService.show_screen(message.chat.id, get_text("start.choose_language", lang), reply_markup=kb)


@router.callback_query(F.data.startswith("lang:"))
async def change_language(callback: CallbackQuery, session: AsyncSession, db_user, state: FSMContext):
    new_lang = callback.data.split(":")[1]
    if db_user:
        user_repo = UserRepository(session)
        await user_repo.update_language(db_user.telegram_id, new_lang)

    # Show welcome message with main menu
    welcome = get_text("start.welcome", new_lang, name=callback.from_user.first_name)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=welcome,
        reply_markup=main_menu_keyboard(new_lang)
    )
    await callback.answer()
