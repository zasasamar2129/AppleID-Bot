from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_keyboard
from app.bot.keyboards.unlock import iphone_series_keyboard, skip_keyboard, yes_no_keyboard
from app.localization import get_text
from app.services.notification_service import NotificationService
from app.services.unlock_service import UnlockService
from app.states.unlock import AppleUnlockStates
from app.utils.message_manager import MessageCleanupService
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
IMEI_RE = re.compile(r"^\d{15}$")


# ---------- Helpers ----------

def mask_email(email: str) -> str:
    """exa***@email.com"""
    at = email.find("@")
    if at <= 1:
        return email
    return email[: min(at, 3)] + "***" + email[at:]


def mask_imei(imei: str) -> str:
    """***********2345"""
    if len(imei) <= 4:
        return imei
    return "*" * (len(imei) - 4) + imei[-4:]


def _series_label(series: str, lang: str) -> str:
    return get_text(f"unlock.series.{series}", lang)


async def _close(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    """Close the unlock flow: clear FSM, cleanup UI, return to main menu."""
    from app.bot.keyboards.main_menu import main_menu_keyboard
    await state.clear()
    await MessageCleanupService.cleanup_user_ui(callback.message.chat.id)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("common.cancelled", lang),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


async def _render_summary(callback_or_message, state: FSMContext, lang: str) -> None:
    """Show the confirmation summary with Edit/Back/Close."""
    data = await state.get_data()
    series = data.get("series")
    email_access = data.get("email_access")
    apple_id_email = data.get("apple_id_email", "")
    password = data.get("apple_id_password")
    imei = data.get("imei", "")
    other_locked = data.get("other_iphone_locked")
    phone_number = data.get("phone_number", "")
    additional = data.get("additional_information")

    yes_no = lambda val: get_text("unlock.yes", lang) if val else get_text("unlock.no", lang)  # noqa: E731

    text = (
        f"🔓 {get_text('unlock.request_title', lang)}\n\n"
        f"📱 {get_text('unlock.summary_series', lang)}: {_series_label(series, lang)}\n"
        f"📧 {get_text('unlock.summary_email_access', lang)}: {'✅ ' + yes_no(email_access)}\n"
        f"📧 {get_text('unlock.summary_email', lang)}: {mask_email(apple_id_email)}\n"
        f"🔐 {get_text('unlock.summary_password', lang)}: "
        + (get_text("unlock.summary_password_set", lang) if password else get_text("unlock.summary_password_skipped", lang))
        + f"\n"
        f"📱 {get_text('unlock.summary_imei', lang)}: {mask_imei(imei)}\n"
        f"📱 {get_text('unlock.summary_other_locked', lang)}: {'❌ ' + yes_no(other_locked)}\n"
        f"📞 {get_text('unlock.summary_phone', lang)}: {phone_number or get_text('unlock.summary_none', lang)}\n\n"
        f"📝 {get_text('unlock.summary_additional', lang)}:\n"
        f"{(additional or get_text('unlock.summary_none', lang))}\n\n"
        f"💳 {get_text('unlock.payment_rule_title', lang)}:\n"
        f"{get_text('unlock.payment_after_admin', lang)}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ {get_text('unlock.confirm_submit', lang)}", callback_data="unlock:submit")
    kb.button(text=f"✏️ {get_text('unlock.edit', lang)}", callback_data="unlock:edit")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="unlock:back_from_confirm")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="unlock:close")
    kb.adjust(1)

    if isinstance(callback_or_message, CallbackQuery):
        await MessageCleanupService.show_screen(callback_or_message.message.chat.id, text, reply_markup=kb.as_markup())
        await callback_or_message.answer()
    else:
        await MessageCleanupService.show_screen(callback_or_message.chat.id, text, reply_markup=kb.as_markup())


def _edit_keyboard(lang: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📱 {get_text('unlock.edit_series', lang)}", callback_data="unlock:edit:series")
    kb.button(text=f"📧 {get_text('unlock.edit_email_access', lang)}", callback_data="unlock:edit:email_access")
    kb.button(text=f"📧 {get_text('unlock.edit_email', lang)}", callback_data="unlock:edit:email")
    kb.button(text=f"🔐 {get_text('unlock.edit_password', lang)}", callback_data="unlock:edit:password")
    kb.button(text=f"📱 {get_text('unlock.edit_imei', lang)}", callback_data="unlock:edit:imei")
    kb.button(text=f"📱 {get_text('unlock.edit_other_locked', lang)}", callback_data="unlock:edit:other")
    kb.button(text=f"📞 {get_text('unlock.edit_phone', lang)}", callback_data="unlock:edit:phone")
    kb.button(text=f"📝 {get_text('unlock.edit_additional', lang)}", callback_data="unlock:edit:additional")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="unlock:back_to_confirm")
    kb.adjust(1)
    return kb


# ---------- Entry ----------

@router.callback_query(F.data == "menu:unlock_apple_id")
async def unlock_entry(callback: CallbackQuery, lang: str = "fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📝 {get_text('unlock.new_request', lang)}", callback_data="unlock:new")
    kb.button(text=f"📋 {get_text('unlock.past_inquiry', lang)}", callback_data="unlock:past")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.menu", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


# ---------- Past requests (UnlockRequest model) ----------

@router.callback_query(F.data == "unlock:past")
async def past_inquiries(callback: CallbackQuery, session: AsyncSession, db_user, state: FSMContext, lang: str = "fa"):
    service = UnlockService(session)
    requests = await service.get_requests_for_user(db_user.id, limit=20)
    if not requests:
        await callback.answer(get_text("unlock.no_past_inquiries", lang), show_alert=True)
        return

    text = f"📋 {get_text('unlock.past_inquiries_list', lang)}\n\n"
    kb = InlineKeyboardBuilder()
    for req in requests:
        text += f"🧾 #{req.id} | {_series_label(req.iphone_series, lang)} | {get_text('unlock.status', lang)}: {req.status.value}\n"
        kb.button(text=f"🧾 #{req.id}", callback_data=f"unlock:req_detail:{req.id}")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:unlock_apple_id")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unlock:req_detail:"))
async def past_inquiry_detail(callback: CallbackQuery, session: AsyncSession, db_user, lang: str = "fa"):
    import re as _re
    m = _re.match(r"unlock:req_detail:(\d+)", callback.data)
    if not m:
        await callback.answer(get_text("unlock.not_found", lang), show_alert=True)
        return
    request_id = int(m.group(1))
    service = UnlockService(session)
    req = await service.get_request(request_id)
    # Ownership check: only the request owner can view it.
    if not req or req.user_id != db_user.id:
        await callback.answer(get_text("unlock.not_found", lang), show_alert=True)
        return

    email_access = get_text("unlock.yes", lang) if req.email_access else get_text("unlock.no", lang)
    other_locked = get_text("unlock.yes", lang) if req.other_iphone_locked else get_text("unlock.no", lang)
    password_label = get_text("unlock.summary_password_set", lang) if req.apple_id_password_encrypted else get_text("unlock.summary_password_skipped", lang)

    text = (
        f"🔓 {get_text('unlock.request_title', lang)}\n\n"
        f"📱 {get_text('unlock.summary_series', lang)}: {_series_label(req.iphone_series, lang)}\n"
        f"📧 {get_text('unlock.summary_email_access', lang)}: {email_access}\n"
        f"📧 {get_text('unlock.summary_email', lang)}: {mask_email(service.get_email(req) or '')}\n"
        f"🔐 {get_text('unlock.summary_password', lang)}: {password_label}\n"
        f"📱 {get_text('unlock.summary_imei', lang)}: {mask_imei(req.imei)}\n"
        f"📱 {get_text('unlock.summary_other_locked', lang)}: {other_locked}\n"
        f"📞 {get_text('unlock.summary_phone', lang)}: {req.phone_number or get_text('unlock.summary_none', lang)}\n"
        f"🟡 {get_text('unlock.status', lang)}: {req.status.value}\n"
        f"📅 {get_text('unlock.date', lang)}: {req.created_at.strftime('%Y/%m/%d')}\n"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="unlock:past")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


# ---------- Start new request ----------

@router.callback_query(F.data == "unlock:new")
async def new_request(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await state.clear()
    kb = iphone_series_keyboard(lang)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.select_series", lang),
        reply_markup=kb,
    )
    await state.set_state(AppleUnlockStates.select_model)
    await callback.answer()


@router.callback_query(AppleUnlockStates.select_model, F.data.startswith("unlock:series:"))
async def select_series(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    series = callback.data.split(":", 2)[2]
    if series not in ("iphone_17", "iphone_16", "iphone_15", "iphone_14", "iphone_13", "iphone_12", "iphone_11", "iphone_x_or_older"):
        await callback.answer(get_text("unlock.invalid_selection", lang), show_alert=True)
        return
    await state.update_data(series=series)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.email_access_question", lang),
        reply_markup=yes_no_keyboard("unlock:email_access", lang),
    )
    await state.set_state(AppleUnlockStates.email_access)
    await callback.answer()


# ---------- Email access Y/N ----------

@router.callback_query(AppleUnlockStates.email_access, F.data.startswith("unlock:email_access:"))
async def email_access_answer(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    value = callback.data.split(":")[2]
    await state.update_data(email_access=(value == "yes"))
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.enter_email", lang),
        reply_markup=cancel_keyboard("unlock:close", lang),
    )
    await state.set_state(AppleUnlockStates.apple_id_email)
    await callback.answer()


# ---------- Email (message) ----------

@router.message(AppleUnlockStates.apple_id_email)
async def enter_email(message: Message, state: FSMContext, lang: str = "fa"):
    email = message.text.strip().lower()
    if not EMAIL_RE.match(email):
        await message.answer(get_text("unlock.invalid_email", lang))
        return
    await state.update_data(apple_id_email=email)
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=get_text("unlock.enter_password", lang),
        reply_markup=skip_keyboard("unlock:password:skip", lang),
    )
    await state.set_state(AppleUnlockStates.apple_id_password)


# ---------- Password (optional) ----------

@router.message(AppleUnlockStates.apple_id_password)
async def enter_password(message: Message, state: FSMContext, lang: str = "fa"):
    password = message.text
    if not password or not password.strip():
        await message.answer(get_text("unlock.invalid_input", lang))
        return
    # Store only the raw string in FSM; it is encrypted on submit.
    await state.update_data(apple_id_password=password.strip())
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=get_text("unlock.enter_imei", lang),
        reply_markup=cancel_keyboard("unlock:close", lang),
    )
    await state.set_state(AppleUnlockStates.imei)


@router.callback_query(AppleUnlockStates.apple_id_password, F.data == "unlock:password:skip")
async def skip_password(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await state.update_data(apple_id_password=None)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.enter_imei", lang),
        reply_markup=cancel_keyboard("unlock:close", lang),
    )
    await state.set_state(AppleUnlockStates.imei)
    await callback.answer()


# ---------- IMEI ----------

@router.message(AppleUnlockStates.imei)
async def enter_imei(message: Message, state: FSMContext, lang: str = "fa"):
    imei = message.text.strip()
    if not IMEI_RE.match(imei):
        await message.answer(get_text("unlock.invalid_imei", lang))
        return
    await state.update_data(imei=imei)
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=get_text("unlock.other_locked_question", lang),
        reply_markup=yes_no_keyboard("unlock:other_locked", lang),
    )
    await state.set_state(AppleUnlockStates.other_iphone_locked)


# ---------- Other iPhone locked Y/N ----------

@router.callback_query(AppleUnlockStates.other_iphone_locked, F.data.startswith("unlock:other_locked:"))
async def other_locked_answer(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    value = callback.data.split(":")[2]
    await state.update_data(other_iphone_locked=(value == "yes"))
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.enter_phone", lang),
        reply_markup=cancel_keyboard("unlock:close", lang),
    )
    await state.set_state(AppleUnlockStates.phone_number)
    await callback.answer()


# ---------- Phone number ----------

PHONE_RE = re.compile(r"^[+]?[0-9\s\-()]{7,20}$")


@router.message(AppleUnlockStates.phone_number)
async def enter_phone_number(message: Message, state: FSMContext, lang: str = "fa"):
    phone = message.text.strip()
    if not PHONE_RE.match(phone):
        await message.answer(get_text("unlock.invalid_phone", lang))
        return
    await state.update_data(phone_number=phone)
    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=get_text("unlock.additional_info", lang),
        reply_markup=skip_keyboard("unlock:additional:skip", lang),
    )
    await state.set_state(AppleUnlockStates.additional_information)


# ---------- Additional information (optional) ----------

@router.message(AppleUnlockStates.additional_information)
async def enter_additional(message: Message, state: FSMContext, lang: str = "fa"):
    additional = message.text.strip()
    if len(additional) > 4000:
        await message.answer(get_text("unlock.additional_too_long", lang))
        return
    await state.update_data(additional_information=additional)
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


@router.callback_query(AppleUnlockStates.additional_information, F.data == "unlock:additional:skip")
async def skip_additional(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await state.update_data(additional_information=None)
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# ---------- Confirm / submit ----------

@router.callback_query(AppleUnlockStates.confirm, F.data == "unlock:submit")
async def submit_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang: str = "fa"):
    data = await state.get_data()
    # Re-validate entire payload before submit.
    series = data.get("series")
    email_access = data.get("email_access")
    apple_id_email = data.get("apple_id_email")
    imei = data.get("imei")
    other_locked = data.get("other_iphone_locked")
    if not series or email_access is None or not apple_id_email or not imei or other_locked is None:
        await callback.answer(get_text("unlock.invalid_incomplete", lang), show_alert=True)
        return

    service = UnlockService(session)
    req = await service.create_request(
        user_id=db_user.id,
        telegram_user_id=db_user.telegram_id,
        iphone_series=series,
        email_access=email_access,
        apple_id_email=apple_id_email,
        apple_id_password=data.get("apple_id_password"),
        imei=imei,
        other_iphone_locked=other_locked,
        additional_information=data.get("additional_information"),
        phone_number=data.get("phone_number"),
    )

    await state.clear()

    # Reply to customer
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🏠 {get_text('common.main_menu', lang)}", callback_data="menu:main")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.submitted_success", lang, request_id=req.id),
        reply_markup=kb.as_markup(),
    )

    # Notify admins
    notifier = NotificationService(callback.bot)
    for admin_id in settings.admin_ids_list:
        try:
            await callback.bot.send_message(
                admin_id,
                get_text(
                    "unlock.admin_notify",
                    lang,
                    request_id=req.id,
                    series=_series_label(series, lang),
                    email_access="✅ " + get_text("unlock.yes", lang) if email_access else "❌ " + get_text("unlock.no", lang),
                    other_locked="✅ " + get_text("unlock.yes", lang) if other_locked else "❌ " + get_text("unlock.no", lang),
                ),
                reply_markup=_admin_view_keyboard(req.id, lang),
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about unlock request: {e}")

    await callback.answer()


def _admin_view_keyboard(request_id: int, lang: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"👁 {get_text('unlock.admin_view', lang)}", callback_data=f"admin_unlock:view:{request_id}")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Edit ----------

@router.callback_query(AppleUnlockStates.confirm, F.data == "unlock:edit")
async def edit_request(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    kb = _edit_keyboard(lang)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.edit_help", lang),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(AppleUnlockStates.edit_select)
    await callback.answer()


@router.callback_query(AppleUnlockStates.edit_select, F.data.startswith("unlock:edit:"))
async def edit_field(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    field = callback.data.split(":")[2]
    if field == "series":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.select_series", lang), reply_markup=iphone_series_keyboard(lang))
        await state.set_state(AppleUnlockStates.edit_series)
        await callback.answer()
    elif field == "email_access":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.email_access_question_short", lang), reply_markup=yes_no_keyboard("unlock:edit_email_access", lang))
        await state.set_state(AppleUnlockStates.edit_email_access)
        await callback.answer()
    elif field == "email":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.enter_email", lang), reply_markup=cancel_keyboard("unlock:close", lang))
        await state.set_state(AppleUnlockStates.edit_apple_id_email)
        await callback.answer()
    elif field == "password":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.enter_password", lang), reply_markup=skip_keyboard("unlock:edit_password:skip", lang))
        await state.set_state(AppleUnlockStates.edit_apple_id_password)
        await callback.answer()
    elif field == "imei":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.enter_imei", lang), reply_markup=cancel_keyboard("unlock:close", lang))
        await state.set_state(AppleUnlockStates.edit_imei)
        await callback.answer()
    elif field == "other":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.other_locked_question", lang), reply_markup=yes_no_keyboard("unlock:edit_other", lang))
        await state.set_state(AppleUnlockStates.edit_other_locked)
        await callback.answer()
    elif field == "phone":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.enter_phone", lang), reply_markup=cancel_keyboard("unlock:close", lang))
        await state.set_state(AppleUnlockStates.edit_phone_number)
        await callback.answer()
    elif field == "additional":
        await MessageCleanupService.show_screen(callback.message.chat.id, get_text("unlock.additional_info", lang), reply_markup=skip_keyboard("unlock:edit_additional:skip", lang))
        await state.set_state(AppleUnlockStates.edit_additional)
        await callback.answer()


# --- Edit: series ---
@router.callback_query(AppleUnlockStates.edit_series, F.data.startswith("unlock:series:"))
async def edit_series_done(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    series = callback.data.split(":", 2)[2]
    if series not in ("iphone_17", "iphone_16", "iphone_15", "iphone_14", "iphone_13", "iphone_12", "iphone_11", "iphone_x_or_older"):
        await callback.answer(get_text("unlock.invalid_selection", lang), show_alert=True)
        return
    await state.update_data(series=series)
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: email access ---
@router.callback_query(AppleUnlockStates.edit_email_access, F.data.startswith("unlock:edit_email_access:"))
async def edit_email_access_done(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    value = callback.data.split(":")[2]
    await state.update_data(email_access=(value == "yes"))
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: email ---
@router.message(AppleUnlockStates.edit_apple_id_email)
async def edit_email_done(message: Message, state: FSMContext, lang: str = "fa"):
    email = message.text.strip().lower()
    if not EMAIL_RE.match(email):
        await message.answer(get_text("unlock.invalid_email", lang))
        return
    await state.update_data(apple_id_email=email)
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: password ---
@router.message(AppleUnlockStates.edit_apple_id_password)
async def edit_password_done(message: Message, state: FSMContext, lang: str = "fa"):
    if not message.text.strip():
        await message.answer(get_text("unlock.invalid_input", lang))
        return
    await state.update_data(apple_id_password=message.text.strip())
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


@router.callback_query(AppleUnlockStates.edit_apple_id_password, F.data == "unlock:edit_password:skip")
async def edit_password_skip(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await state.update_data(apple_id_password=None)
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: imei ---
@router.message(AppleUnlockStates.edit_imei)
async def edit_imei_done(message: Message, state: FSMContext, lang: str = "fa"):
    imei = message.text.strip()
    if not IMEI_RE.match(imei):
        await message.answer(get_text("unlock.invalid_imei", lang))
        return
    await state.update_data(imei=imei)
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: other locked ---
@router.callback_query(AppleUnlockStates.edit_other_locked, F.data.startswith("unlock:edit_other:"))
async def edit_other_done(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    value = callback.data.split(":")[2]
    await state.update_data(other_iphone_locked=(value == "yes"))
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: phone number ---
@router.message(AppleUnlockStates.edit_phone_number)
async def edit_phone_done(message: Message, state: FSMContext, lang: str = "fa"):
    phone = message.text.strip()
    if not PHONE_RE.match(phone):
        await message.answer(get_text("unlock.invalid_phone", lang))
        return
    await state.update_data(phone_number=phone)
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# --- Edit: additional ---
@router.message(AppleUnlockStates.edit_additional)
async def edit_additional_done(message: Message, state: FSMContext, lang: str = "fa"):
    additional = message.text.strip()
    if len(additional) > 4000:
        await message.answer(get_text("unlock.additional_too_long", lang))
        return
    await state.update_data(additional_information=additional)
    await _render_summary(message, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


@router.callback_query(AppleUnlockStates.edit_additional, F.data == "unlock:edit_additional:skip")
async def edit_additional_skip(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await state.update_data(additional_information=None)
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# ---------- Back handling ----------

@router.callback_query(AppleUnlockStates.confirm, F.data == "unlock:back_from_confirm")
async def back_from_confirm(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    # Go back to additional info step
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("unlock.additional_info", lang),
        reply_markup=skip_keyboard("unlock:additional:skip", lang),
    )
    await state.set_state(AppleUnlockStates.additional_information)
    await callback.answer()


@router.callback_query(AppleUnlockStates.edit_select, F.data == "unlock:back_to_confirm")
async def back_to_confirm(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await _render_summary(callback, state, lang)
    await state.set_state(AppleUnlockStates.confirm)


# ---------- Close / cancel ----------

@router.callback_query(F.data == "unlock:close")
async def close_flow(callback: CallbackQuery, state: FSMContext, lang: str = "fa"):
    await _close(callback, state, lang)


# `/cancel` is handled globally in start.py — it clears FSM and returns to main menu.