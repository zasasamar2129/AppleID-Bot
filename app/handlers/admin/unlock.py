from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.enums import UnlockPaymentStatus, UnlockRequestStatus
from app.database.repositories.user_repo import UserRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.services.notification_service import NotificationService
from app.services.unlock_service import UnlockService, IPHONE_SERIES_ORDER
from app.states.admin.unlock import AdminUnlockStates
from app.utils.formatting import format_price

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


def _series_label(series: str, lang: str) -> str:
    return get_text(f"unlock.series.{series}", lang)


def _status_label(status: UnlockRequestStatus, lang: str) -> str:
    return get_text(f"unlock_admin.status.{status.value}", lang, default=status.value)


def _payment_label(status: UnlockPaymentStatus, lang: str) -> str:
    return get_text(f"unlock_admin.payment.{status.value}", lang, default=status.value)


@router.callback_query(F.data == "admin:unlock_requests")
async def unlock_requests_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    service = UnlockService(session)
    requests = await service.get_all_requests(limit=30)
    if not requests:
        await callback.message.edit_text(get_text("unlock_admin.none", lang, default="No unlock requests found."))
        await callback.answer()
        return

    text = f"🔓 {get_text('unlock_admin.title', lang)}\n\n"
    kb = InlineKeyboardBuilder()
    for req in requests:
        user = await UserRepository(session).get_by_id(req.user_id)
        user_name = (user.first_name or "") if user else f"#{req.user_id}"
        status_icon = "🟡"
        if req.status in (UnlockRequestStatus.COMPLETED,):
            status_icon = "🟢"
        elif req.status in (UnlockRequestStatus.REJECTED, UnlockRequestStatus.CANCELLED):
            status_icon = "🔴"
        text += f"{status_icon} #{req.id} {user_name} | {_series_label(req.iphone_series, lang)} | {_status_label(req.status, lang)}\n"
        kb.button(text=f"#{req.id}", callback_data=f"admin_unlock:view:{req.id}")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unlock:view:"))
async def unlock_request_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    service = UnlockService(session)
    req = await service.get_request(request_id)
    if not req:
        await callback.answer(get_text("unlock_admin.not_found", lang, default="Request not found"), show_alert=True)
        return

    user = await UserRepository(session).get_by_id(req.user_id)
    user_name = f"{user.first_name} {user.last_name or ''}" if user else f"#{req.user_id}"
    user_tg = user.telegram_id if user else req.telegram_user_id
    email_access = get_text("unlock.yes", lang) if req.email_access else get_text("unlock.no", lang)
    other_locked = get_text("unlock.yes", lang) if req.other_iphone_locked else get_text("unlock.no", lang)

    text = (
        f"🔓 {get_text('unlock_admin.title', lang)}\n\n"
        f"🧾 #{req.id}\n"
        f"👤 {user_name} (tg: {user_tg})\n"
        f"📱 {get_text('unlock_admin.series', lang)}: {_series_label(req.iphone_series, lang)}\n"
        f"📧 {get_text('unlock_admin.email_access', lang)}: {email_access}\n"
        f"📱 IMEI: {req.imei}\n"
        f"📱 {get_text('unlock_admin.other_locked', lang)}: {other_locked}\n"
        f"📞 {get_text('unlock_admin.phone', lang)}: {req.phone_number or '—'}\n"
        f"💳 {get_text('unlock_admin.payment', lang)}: {_payment_label(req.payment_status, lang)}\n"
        f"🟡 {get_text('unlock_admin.status', lang)}: {_status_label(req.status, lang)}\n"
        f"📅 {get_text('unlock_admin.created', lang)}: {req.created_at.strftime('%Y/%m/%d %H:%M')}\n"
    )
    if req.additional_information:
        text += f"📝 {get_text('unlock_admin.additional', lang)}: {req.additional_information}\n"
    if req.admin_notes:
        text += f"🗒 {get_text('unlock_admin.notes', lang)}: {req.admin_notes}\n"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"👁 {get_text('unlock_admin.view_creds', lang)}", callback_data=f"admin_unlock:creds:{req.id}")
    kb.button(text=f"💳 {get_text('unlock_admin.request_payment', lang)}", callback_data=f"admin_unlock:pay_req:{req.id}")
    kb.button(text=f"🔄 {get_text('unlock_admin.change_status', lang)}", callback_data=f"admin_unlock:status:{req.id}")
    kb.button(text=f"📝 {get_text('unlock_admin.add_note', lang)}", callback_data=f"admin_unlock:note:{req.id}")
    kb.button(text=f"✅ {get_text('unlock_admin.complete', lang)}", callback_data=f"admin_unlock:complete:{req.id}")
    kb.button(text=f"❌ {get_text('unlock_admin.reject', lang)}", callback_data=f"admin_unlock:reject:{req.id}")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="admin:unlock_requests")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unlock:creds:"))
async def unlock_request_creds(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    """Permission-protected credential view (admin only, already filtered)."""
    request_id = int(callback.data.split(":")[2])
    service = UnlockService(session)
    req = await service.get_request(request_id)
    if not req:
        await callback.answer(get_text("unlock_admin.not_found", lang, default="Request not found"), show_alert=True)
        return

    email = service.get_email(req)
    password = service.get_password(req)
    text = (
        f"🔐 {get_text('unlock_admin.creds_title', lang)}\n\n"
        f"🧾 #{req.id}\n"
        f"📧 Email: {email or '—'}\n"
        f"🔑 Password: {password or '—'}\n\n"
        f"⚠️ {get_text('unlock_admin.creds_warning', lang)}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data=f"admin_unlock:view:{req.id}")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unlock:pay_req:"))
async def request_payment_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    await state.update_data(request_id=request_id)
    await callback.message.edit_text(get_text("unlock_admin.pay_amount_prompt", lang, default="Enter the payment amount (number):"))
    await state.set_state(AdminUnlockStates.PAYMENT_AMOUNT)
    await callback.answer()


@router.message(AdminUnlockStates.PAYMENT_AMOUNT)
async def request_payment_amount(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer(get_text("unlock_admin.invalid_amount", lang, default="Invalid amount."))
        return
    data = await state.get_data()
    request_id = data["request_id"]
    service = UnlockService(session)
    req = await service.request_payment(request_id, amount=float(amount), admin_id=message.from_user.id)

    if not req:
        await message.answer(get_text("unlock_admin.not_found", lang, default="Request not found."))
        await state.clear()
        return

    audit = AuditService(session)
    await audit.log(
        admin_telegram_id=message.from_user.id,
        action="unlock_request_payment",
        target_type="unlock_request",
        target_id=str(request_id),
        metadata={"amount": str(amount)},
    )

    # Notify the customer
    user = await UserRepository(session).get_by_id(req.user_id)
    notifier = NotificationService(message.bot)
    if user:
        try:
            await message.bot.send_message(
                user.telegram_id,
                get_text("unlock_admin.pay_notify_customer", lang, request_id=req.id, amount=format_price(amount, lang)),
            )
        except Exception as e:
            logger.error(f"Failed to notify customer for unlock payment: {e}")

    await message.answer(get_text("unlock_admin.pay_requested", lang, request_id=req.id, default=f"Payment requested for request #{req.id}."))
    await state.clear()


@router.callback_query(F.data.startswith("admin_unlock:status:"))
async def change_status(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    kb = InlineKeyboardBuilder()
    statuses = [
        UnlockRequestStatus.UNDER_REVIEW,
        UnlockRequestStatus.WAITING_FOR_CUSTOMER,
        UnlockRequestStatus.IN_PROGRESS,
        UnlockRequestStatus.COMPLETED,
        UnlockRequestStatus.REJECTED,
        UnlockRequestStatus.CANCELLED,
    ]
    for st in statuses:
        kb.button(text=_status_label(st, lang), callback_data=f"admin_unlock:set_status:{request_id}:{st.value}")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data=f"admin_unlock:view:{request_id}")
    kb.adjust(1)
    await callback.message.edit_text(get_text("unlock_admin.choose_status", lang, default="Choose new status:"), reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unlock:set_status:"))
async def set_status(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    parts = callback.data.split(":")
    request_id = int(parts[2])
    status_value = parts[3]
    try:
        status = UnlockRequestStatus(status_value)
    except ValueError:
        await callback.answer(get_text("unlock_admin.invalid_status", lang, default="Invalid status"), show_alert=True)
        return
    service = UnlockService(session)
    req = await service.set_status(request_id, status, admin_id=callback.from_user.id)
    if not req:
        await callback.answer(get_text("unlock_admin.not_found", lang, default="Request not found"), show_alert=True)
        return

    audit = AuditService(session)
    await audit.log(
        admin_telegram_id=callback.from_user.id,
        action="unlock_request_status",
        target_type="unlock_request",
        target_id=str(request_id),
        metadata={"status": status.value},
    )
    await callback.answer(get_text("unlock_admin.status_changed", lang, default="Status updated."), show_alert=True)
    callback.data = f"admin_unlock:view:{request_id}"
    await unlock_request_detail(callback, session, lang)


@router.callback_query(F.data.startswith("admin_unlock:note:"))
async def add_note_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    await state.update_data(request_id=request_id)
    await callback.message.edit_text(get_text("unlock_admin.note_prompt", lang, default="Enter the note:"))
    await state.set_state(AdminUnlockStates.ADD_NOTE)
    await callback.answer()


@router.message(AdminUnlockStates.ADD_NOTE)
async def add_note_done(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    request_id = data["request_id"]
    service = UnlockService(session)
    await service.add_note(request_id, message.text.strip(), admin_id=message.from_user.id)
    await message.answer(get_text("unlock_admin.note_added", lang, default="✅ Note added."))
    await state.clear()


@router.callback_query(F.data.startswith("admin_unlock:complete:"))
async def complete_request(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    service = UnlockService(session)
    req = await service.complete(request_id, admin_id=callback.from_user.id)
    if not req:
        await callback.answer(get_text("unlock_admin.not_found", lang, default="Request not found"), show_alert=True)
        return
    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="unlock_request_complete", target_type="unlock_request", target_id=str(request_id))
    await callback.answer(get_text("unlock_admin.completed", lang, default="✅ Request completed."), show_alert=True)
    callback.data = f"admin_unlock:view:{request_id}"
    await unlock_request_detail(callback, session, lang)


@router.callback_query(F.data.startswith("admin_unlock:reject:"))
async def reject_request(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    request_id = int(callback.data.split(":")[2])
    service = UnlockService(session)
    req = await service.reject(request_id, admin_id=callback.from_user.id)
    if not req:
        await callback.answer(get_text("unlock_admin.not_found", lang, default="Request not found"), show_alert=True)
        return
    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="unlock_request_reject", target_type="unlock_request", target_id=str(request_id))
    await callback.answer(get_text("unlock_admin.rejected", lang, default="❌ Request rejected."), show_alert=True)
    callback.data = f"admin_unlock:view:{request_id}"
    await unlock_request_detail(callback, session, lang)