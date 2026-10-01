from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import button
from app.bot.keyboards.common import back_keyboard, cancel_keyboard
from app.database.models.enums import SupportCategory, SupportStatus
from app.localization import get_text
from app.services.support_service import SupportService
from app.states.support import SupportStates
from app.utils.message_manager import MessageCleanupService
from app.utils.support_format import (
    STATUS_ICONS,
    escape,
    render_conversation,
    truncate,
)

router = Router()


async def show_support_menu(message: Message, lang: str = "fa"):
    kb = InlineKeyboardBuilder()
    # "My Tickets" first so an existing conversation is one tap away; a new
    # ticket is the longer flow.
    kb.add(
        button(
            get_text("support.create_ticket", lang),
            callback_data="support:new",
            style="primary",
            lang=lang,
        )
    )
    kb.add(
        button(
            get_text("support.my_tickets", lang),
            callback_data="support:my",
            style="success",
            lang=lang,
        )
    )
    kb.add(
        button(
            get_text("common.cancel", lang),
            callback_data="menu:main",
            style="danger",
            emoji_key="cancel",
            lang=lang,
        )
    )
    kb.adjust(1)  # Single column format
    # Tracked so it is edited/cleaned on Back/Main.
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("support.how_can_help", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )


async def _show_categories(message: Message, lang: str = "fa") -> None:
    """Category picker for a new ticket."""
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
    kb.add(
        button(
            get_text("common.back", lang),
            callback_data="menu:support",
            lang=lang,
        )
    )
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("support.select_category", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )


@router.callback_query(F.data == "support:new")
async def support_new_ticket(callback: CallbackQuery, lang="fa"):
    await _show_categories(callback.message, lang)
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
async def support_message(
    message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"
):
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


# ---------------------------------------------------------------------------
# My Tickets
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "support:my")
async def support_my_tickets(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    tickets = await SupportService(session).get_user_tickets(db_user.id)
    if not tickets:
        await MessageCleanupService.show_screen(
            callback.message.chat.id,
            get_text("support.no_tickets", lang),
            reply_markup=back_keyboard("menu:support", lang),
            force_new=True,
        )
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for ticket in tickets[:10]:
        icon = STATUS_ICONS.get(ticket.status, "•")
        label = f"{icon} #{ticket.id} · {truncate(ticket.subject, 30)}"
        kb.button(text=label, callback_data=f"support:t:{ticket.id}")
    kb.button(text=get_text("common.back", lang), callback_data="menu:support")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        get_text("support.my_tickets", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support:t:"))
async def support_ticket_detail(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    ticket_id = int(callback.data.split(":")[2])
    service = SupportService(session)
    ticket = await service.get_ticket(ticket_id)
    # Ownership check: without it any user could read another's ticket by
    # guessing an id.
    if not ticket or ticket.user_id != db_user.id:
        await callback.answer(
            get_text("errors.not_found", lang, default="Not found"), show_alert=True
        )
        return

    messages = await service.get_messages_paginated(ticket_id, limit=20, offset=0)
    header = f"{STATUS_ICONS.get(ticket.status, '•')} Ticket #{ticket.id}\n"
    header += f"{get_text('support.ticket_status', lang, status=ticket.status.value)}\n"
    header += f"📌 {escape(ticket.subject)}\n\n"
    header += render_conversation(messages)

    kb = InlineKeyboardBuilder()
    if ticket.status in (SupportStatus.OPEN, SupportStatus.WAITING_USER, SupportStatus.IN_PROGRESS):
        kb.button(
            text=get_text("support.reply", lang, default="Reply"),
            callback_data=f"support:reply:{ticket.id}",
        )
    kb.button(text=get_text("common.back", lang), callback_data="support:my")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        header,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support:reply:"))
async def support_reply_prompt(callback: CallbackQuery, state: FSMContext, lang="fa"):
    ticket_id = int(callback.data.split(":")[2])
    await state.update_data(reply_ticket_id=ticket_id)
    await MessageCleanupService.send_temporary(
        callback.message.chat.id,
        get_text("support.reply", lang, default="Enter your reply:"),
        reply_markup=cancel_keyboard("support:my", lang),
    )
    await state.set_state(SupportStates.REPLY)
    await callback.answer()


@router.message(SupportStates.REPLY)
async def support_reply_send(
    message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"
):
    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    body = (message.text or "").strip()
    await state.clear()
    if not ticket_id or not body:
        return

    service = SupportService(session)
    ticket = await service.get_ticket(ticket_id)
    if not ticket or ticket.user_id != db_user.id:
        await message.answer(get_text("errors.not_found", lang, default="Not found"))
        return

    await service.reply_user(ticket_id, db_user.id, body)
    await service.update_status(ticket_id, SupportStatus.OPEN)

    messages = await service.get_messages_paginated(ticket_id, limit=20, offset=0)
    header = f"{STATUS_ICONS.get(ticket.status, '•')} Ticket #{ticket.id}\n"
    header += f"📌 {escape(ticket.subject)}\n\n"
    header += render_conversation(messages)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=get_text("support.my_tickets", lang),
        callback_data="support:my",
    )
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        message.chat.id, header, reply_markup=kb.as_markup(), force_new=True
    )
