"""Admin support panel: ticket list with message previews, threaded detail,
reply, status changes and assignment.

Every relationship read (ticket.user) is eagerly loaded by the repository —
touching a lazy-loaded attribute outside an awaited query raises
sqlalchemy.exc.MissingGreenlet on the event loop.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.bot import bot
from app.bot.filters.admin import IsAdmin
from app.database.models.enums import SupportStatus
from app.database.repositories.admin_repo import AdminRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.services.support_service import SupportService
from app.states.admin.support import AdminSupportStates
from app.utils.support_format import (
    CATEGORY_ICONS,
    STATUS_ICONS,
    escape,
    relative_time,
    render_conversation,
    truncate,
)

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PER_PAGE = 8
MESSAGES_PER_PAGE = 20

FILTER_ORDER = [
    (None, "All"),
    (SupportStatus.OPEN, "Open"),
    (SupportStatus.IN_PROGRESS, "In Progress"),
    (SupportStatus.WAITING_USER, "Waiting"),
    (SupportStatus.RESOLVED, "Resolved"),
    (SupportStatus.CLOSED, "Closed"),
]


def _parse_status(raw: str | None) -> SupportStatus | None:
    if not raw:
        return None
    try:
        return SupportStatus(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "admin:support")
async def admin_support_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    await _render_list(callback, session, status=None, page=1, lang=lang)


@router.callback_query(F.data.startswith("admin:support:f:"))
async def admin_support_filtered(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    status = _parse_status(callback.data.split(":")[3] or None)
    await _render_list(callback, session, status=status, page=1, lang=lang)


@router.callback_query(F.data.startswith("admin:support:page:"))
async def admin_support_page(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    page = int(callback.data.split(":")[3])
    parts = callback.data.split(":")
    status = _parse_status(parts[4] if len(parts) > 4 else None)
    await _render_list(callback, session, status=status, page=page, lang=lang)


async def _render_list(
    callback: CallbackQuery,
    session: AsyncSession,
    status: SupportStatus | None,
    page: int,
    lang: str = "fa",
) -> None:
    service = SupportService(session)
    total = await service.count_tickets(status)
    counts = await service.count_by_status()
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(1, min(page, pages))

    tickets = await service.get_all_tickets_paginated(
        status, limit=PER_PAGE, offset=(page - 1) * PER_PAGE
    )

    kb = InlineKeyboardBuilder()

    # Filter tabs with per-status counts, laid out explicitly.
    # NOTE: InlineKeyboardBuilder.adjust() re-flows *every* button added so
    # far, so calling it again later would squash these tabs into one column.
    # Rows are therefore built explicitly and never re-adjusted.
    tab_buttons = []
    for value, label in FILTER_ORDER:
        count = counts.get(value, 0) if value else sum(counts.values())
        marker = "✅ " if value == status else ""
        tab_buttons.append(
            InlineKeyboardButton(
                text=f"{marker}{label} {count}",
                callback_data=f"admin:support:f:{value.value if value else 'all'}",
            )
        )
    kb.row(*tab_buttons[0:3])
    kb.row(*tab_buttons[3:6])

    if not tickets:
        await callback.message.edit_text(
            get_text("admin.support.no_tickets", lang, default="No tickets found."),
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
        return

    previews = await service.get_last_messages([t.id for t in tickets])

    for ticket in tickets:
        user = ticket.user  # eagerly loaded by the repository
        who = user.first_name if user else "?"
        cat_icon = CATEGORY_ICONS.get(ticket.category.value, "•")
        preview = previews.get(ticket.id)
        body = truncate(preview.message, 60) if preview else ticket.subject
        text = (
            f"#{ticket.id} · {ticket.status.value} · {cat_icon} · "
            f"{relative_time(ticket.updated_at)}\n"
        )
        text += f"👤 {escape(who)}: {escape(body) or escape(ticket.subject)}"
        kb.row(
            InlineKeyboardButton(
                text=truncate(text, 90), callback_data=f"admin:support:t:{ticket.id}"
            )
        )

    # Pagination.
    suffix = status.value if status else "all"
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"admin:support:page:{page - 1}:{suffix}"
            )
        )
    nav.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        nav.append(
            InlineKeyboardButton(
                text="➡️", callback_data=f"admin:support:page:{page + 1}:{suffix}"
            )
        )
    kb.row(*nav)

    kb.row(
        InlineKeyboardButton(
            text=get_text("common.back", lang), callback_data="admin:main"
        )
    )

    await callback.message.edit_text(
        get_text("admin.support.list_title", lang, default="🎧 Support tickets"),
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("admin:support:t:"))
async def admin_support_ticket(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    parts = callback.data.split(":")
    ticket_id = int(parts[3])
    msg_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    await _render_detail(callback, session, ticket_id, msg_page=msg_page, lang=lang)


async def _render_detail(
    callback: CallbackQuery,
    session: AsyncSession,
    ticket_id: int,
    msg_page: int = 0,
    lang: str = "fa",
) -> None:
    service = SupportService(session)
    ticket = await service.get_ticket_with_user(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found", show_alert=True)
        return

    total_msgs = await service.count_messages(ticket_id)
    msg_pages = max(1, (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE)
    msg_page = max(0, min(msg_page, msg_pages - 1))
    messages = await service.get_messages_paginated(
        ticket_id, limit=MESSAGES_PER_PAGE, offset=msg_page * MESSAGES_PER_PAGE
    )

    user = ticket.user
    icon = STATUS_ICONS.get(ticket.status, "•")
    cat_icon = CATEGORY_ICONS.get(ticket.category.value, "•")

    header = f"{icon} Ticket #{ticket.id} · {cat_icon} {ticket.category.value}\n\n"
    if user:
        name = escape(f"{user.first_name} {user.last_name or ''}".strip())
        handle = f" (@{escape(user.username)})" if user.username else ""
        header += f"👤 {name}{handle}\n🆔 {user.telegram_id}\n"
    header += (
        f"🕐 Opened {relative_time(ticket.created_at)} · "
        f"updated {relative_time(ticket.updated_at)}\n"
    )
    header += f"📌 Subject: {escape(ticket.subject)}\n"
    if ticket.admin_id:
        header += "🛠 Assigned\n"
    header += "\n── Conversation ──\n"

    await callback.message.edit_text(
        header + render_conversation(messages),
        reply_markup=_detail_keyboard(ticket, msg_page, msg_pages).as_markup(),
    )
    await callback.answer()


def _detail_keyboard(ticket, msg_page: int, msg_pages: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    suffix = "" if msg_page == 0 else f":{msg_page}"
    kb.row(
        InlineKeyboardButton(
            text="💬 Reply", callback_data=f"admin:support:reply:{ticket.id}"
        ),
        InlineKeyboardButton(
            text="📌 Status", callback_data=f"admin:support:status:{ticket.id}{suffix}"
        ),
    )
    if not ticket.admin_id:
        kb.row(
            InlineKeyboardButton(
                text="🛠 Assign to me",
                callback_data=f"admin:support:assign:{ticket.id}{suffix}",
            )
        )

    if msg_pages > 1:
        nav = []
        if msg_page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️ Older",
                    callback_data=f"admin:support:t:{ticket.id}:{msg_page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(text=f"{msg_page + 1}/{msg_pages}", callback_data="noop")
        )
        if msg_page < msg_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="Newer ➡️",
                    callback_data=f"admin:support:t:{ticket.id}:{msg_page + 1}",
                )
            )
        kb.row(*nav)

    kb.row(
        InlineKeyboardButton(
            text="⬅️ Back to tickets", callback_data="admin:support"
        )
    )
    return kb


# ---------------------------------------------------------------------------
# Status submenu
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("admin:support:status:"))
async def admin_support_status_menu(callback: CallbackQuery, lang="fa"):
    parts = callback.data.split(":")
    ticket_id = int(parts[3])
    msg_page = parts[4] if len(parts) > 4 and parts[4].isdigit() else None

    kb = InlineKeyboardBuilder()
    for status in SupportStatus:
        label_key = f"admin.support.status_{status.value}"
        label = get_text(label_key, lang, default=status.value.replace("_", " ").title())
        kb.row(
            InlineKeyboardButton(
                text=f"{STATUS_ICONS[status]} {label}",
                callback_data=f"admin:support:set:{ticket_id}:{status.value}",
            )
        )
    back = f"admin:support:t:{ticket_id}" + (f":{msg_page}" if msg_page else "")
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=back))

    await callback.message.edit_text(
        get_text("admin.support.status_change", lang, default="Change status:"),
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:support:set:"))
async def admin_support_set_status(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    parts = callback.data.split(":")
    ticket_id = int(parts[3])
    new_status = _parse_status(parts[4])
    if new_status is None:
        await callback.answer("Unknown status", show_alert=True)
        return

    service = SupportService(session)
    await service.update_status(ticket_id, new_status)
    await AuditService(session).log(
        admin_telegram_id=callback.from_user.id,
        action="support_status_change",
        target_type="support_ticket",
        target_id=str(ticket_id),
        metadata={"status": new_status.value},
    )
    await _render_detail(callback, session, ticket_id, lang=lang)


@router.callback_query(F.data.startswith("admin:support:assign:"))
async def admin_support_assign(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    parts = callback.data.split(":")
    ticket_id = int(parts[3])
    msg_page = parts[4] if len(parts) > 4 and parts[4].isdigit() else None

    admin = await AdminRepository(session).get_by_telegram_id(callback.from_user.id)
    if not admin:
        # IsAdmin admits anyone in settings.admin_ids_list; those may have no
        # admin_users row. Surface it instead of failing silently.
        await callback.answer(
            get_text("admin.support.no_admin_record", lang, default="No admin record"),
            show_alert=True,
        )
        return

    await SupportService(session).assign_admin(ticket_id, admin.id)
    await AuditService(session).log(
        admin_telegram_id=callback.from_user.id,
        action="support_assign",
        target_type="support_ticket",
        target_id=str(ticket_id),
    )
    await _render_detail(
        callback, session, ticket_id,
        msg_page=int(msg_page) if msg_page else 0,
        lang=lang,
    )


# ---------------------------------------------------------------------------
# Reply
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("admin:support:reply:"))
async def admin_support_reply_prompt(callback: CallbackQuery, state: FSMContext, lang="fa"):
    ticket_id = int(callback.data.split(":")[3])
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(
        get_text("admin.support.enter_reply", lang, default="Enter your reply:")
    )
    await state.set_state(AdminSupportStates.REPLY)
    await callback.answer()


@router.message(AdminSupportStates.REPLY)
async def admin_support_reply_send(
    message: Message, state: FSMContext, session: AsyncSession, lang="fa"
):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    body = (message.text or "").strip()
    if not ticket_id or not body:
        await state.clear()
        return

    service = SupportService(session)
    ticket = await service.get_ticket_with_user(ticket_id)
    if not ticket:
        await message.answer("Ticket not found")
        await state.clear()
        return

    admin = await AdminRepository(session).get_by_telegram_id(message.from_user.id)
    if not admin:
        logger.warning(
            "Admin %s has no admin_users row; reply recorded without attribution",
            message.from_user.id,
        )

    # Persist first: the DB write is the source of truth, the push is best effort.
    await service.reply_admin(ticket_id, admin.id if admin else None, body)
    await service.update_status(ticket_id, SupportStatus.IN_PROGRESS)
    await AuditService(session).log(
        admin_telegram_id=message.from_user.id,
        action="support_reply",
        target_type="support_ticket",
        target_id=str(ticket_id),
    )

    delivered = await _notify_user(session, ticket, body)
    if not delivered:
        logger.info("User notification not delivered for ticket %s", ticket_id)

    await state.clear()
    await _render_reply_result(message, session, ticket_id, delivered, lang)


async def _notify_user(session, ticket, body: str) -> bool:
    """Push the reply to the customer. Best effort — never loses the reply."""
    user = ticket.user
    if not user:
        return False
    text = (
        f"🎧 <b>Support reply — ticket #{ticket.id}</b>\n\n"
        f"{escape(truncate(body, 1500))}\n\n"
        f"Open My Tickets in the Support menu to reply."
    )
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
        return True
    except Exception as exc:  # noqa: BLE001 - blocked user, network, etc.
        logger.warning(
            "Could not notify user_id=%s of ticket %s: %s",
            user.telegram_id,
            ticket.id,
            type(exc).__name__,
        )
        return False


async def _render_reply_result(
    message: Message, session: AsyncSession, ticket_id: int, delivered: bool, lang: str
) -> None:
    """Replace the prompt with the refreshed conversation."""
    service = SupportService(session)
    ticket = await service.get_ticket_with_user(ticket_id)
    if not ticket:
        return
    messages = await service.get_messages_paginated(
        ticket_id, limit=MESSAGES_PER_PAGE, offset=0
    )
    user = ticket.user
    icon = STATUS_ICONS.get(ticket.status, "•")
    header = f"{icon} Ticket #{ticket.id} · {ticket.status.value}\n\n"
    if user:
        header += f"👤 {escape(user.first_name)}\n"
    if not delivered:
        header += "⚠️ <i>User could not be notified (they may have blocked the bot).</i>\n"
    header += "\n── Conversation ──\n"

    try:
        await message.edit_text(
            header + render_conversation(messages[-MESSAGES_PER_PAGE:]),
            reply_markup=_detail_keyboard(ticket, 0, 1).as_markup(),
        )
    except Exception:  # noqa: BLE001 - the prompt message may be uneditable
        await message.answer(
            get_text("admin.support.reply_sent", lang, default="Reply sent.")
        )
