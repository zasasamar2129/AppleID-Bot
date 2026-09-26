from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import button
from app.localization import get_text
from app.utils.message_manager import MessageCleanupService

router = Router()

async def show_about(message: Message, lang: str = "fa"):
    text = get_text("about.text", lang)
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("common.back", lang), callback_data="menu:main", emoji_key="back", lang=lang))
    await MessageCleanupService.show_screen(message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)

@router.callback_query(F.data == "menu:about")
async def about_callback(callback: CallbackQuery, lang="fa"):
    await show_about(callback.message, lang)
    await callback.answer()
