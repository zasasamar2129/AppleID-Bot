from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import button
from app.bot.keyboards.common import cancel_keyboard
from app.database.models.enums import SupportCategory
from app.localization import get_text
from app.services.support_service import SupportService
from app.states.support import SupportStates
from app.utils.message_manager import MessageCleanupService

router = Router()


async def show_support_menu(message: Message, lang: str = "fa"):
    kb = InlineKeyboardBuilder()
    categories = [
        ("payment", "support.category_payment"),
        ("order", "support.category_order"),
        ("apple_id", "support.category_apple_id"),
        ("wallet", "support.category_wallet"),
        ("other", "support.category_other"),
    ]
    for value, key in categories:
        kb.add(button(get_text(key, lang), callback_data=f"support:cat:{value}", lang=lang))
    kb.add(button(get_text("common.cancel", lang), callback_data="menu:main", style="danger", emoji_key="cancel", lang=lang))
    kb.adjust(1)  # Single column format
    # Tracked so it is edited/cleaned on Back/Main.
    await MessageCleanupService.show_screen(message.chat.id, get_text("support.select_category", lang), reply_markup=kb.as_markup(), force_new=True)


@router.callback_query(F.data == "menu:support")
async def menu_support_callback(callback: CallbackQuery, lang="fa"):
    await show_support_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("support:cat:"))
async def support_category(callback: CallbackQuery, state: FSMContext, lang="fa"):
    cat = callback.data.split(":")[2]
    await state.update_data(category=cat)
    # Tracked as PROMPT so it is removed when the user returns to Main / Cancel.
    await MessageCleanupService.send_temporary(
        callback.message.chat.id,
        get_text("support.enter_subject", lang),
        reply_markup=cancel_keyboard("menu:main", lang),
    )
    await state.set_state(SupportStates.ENTER_SUBJECT)
    await callback.answer()


@router.message(SupportStates.ENTER_SUBJECT)
async def support_subject(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(subject=message.text)
    await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("support.enter_message", lang),
        reply_markup=cancel_keyboard("menu:main", lang),
    )
    await state.set_state(SupportStates.ENTER_MESSAGE)


@router.message(SupportStates.ENTER_MESSAGE)
async def support_message(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    data = await state.get_data()
    support_service = SupportService(session)
    cat = SupportCategory(data.get("category", "other"))
    ticket = await support_service.create_ticket(db_user.id, data["subject"], cat)
    await support_service.reply_user(ticket.id, db_user.id, message.text)
    # A support confirmation is a business record — register it as protected so
    # automatic cleanup never removes it. It also carries the Back/Cancel UI.
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("support.confirm", lang, ticket_id=ticket.id),
        force_new=True,
    )
    await state.clear()