from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.referral_repo import ReferralRepository
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.localization import get_text
from app.states.profile import ProfileStates
from app.utils.formatting import format_price
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def show_profile(message: Message, session: AsyncSession, db_user, lang: str = "fa"):
    user = db_user
    if not user:
        return

    # Repositories
    wallet_repo = WalletRepository(session)
    order_repo = OrderRepository(session)
    referral_repo = ReferralRepository(session)

    wallet = await wallet_repo.get_by_user(user.id)
    orders_count = len(await order_repo.get_by_user(user.id, limit=100))
    referrals_count = await referral_repo.count_referrals(user.id)

    # Language display
    language_display = "فارسی" if user.language == "fa" else "English"
    # VIP status
    vip_display = get_text("profile.vip_yes", lang) if user.is_vip else get_text("profile.vip_no", lang)

    # Fallback values
    full_name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    full_name = full_name.strip() or get_text("profile.not_set", lang)
    username = f"@{user.username}" if user.username else get_text("profile.not_set", lang)
    balance_str = format_price(wallet.balance, lang) if wallet else get_text("profile.not_set", lang)

    # Build polished profile text
    text = (
        f"👤 {get_text('profile.title', lang)}\n\n"
        f"{get_text('profile.greeting', lang, name=full_name)}\n\n"
        f"🪪 {get_text('profile.account_info', lang)}\n"
        f"👤 {get_text('profile.name', lang)}: {full_name}\n"
        f"🔗 {get_text('profile.username', lang)}: {username}\n"
        f"🆔 {get_text('profile.user_id', lang)}: {user.telegram_id}\n"
        f"🌐 {get_text('profile.language', lang)}: {language_display}\n\n"
        f"📅 {get_text('profile.registration_date', lang)}: {user.created_at.strftime('%Y/%m/%d')}\n\n"
        f"💰 {get_text('profile.wallet_balance', lang)}: {balance_str}\n"
        f"📦 {get_text('profile.orders_count', lang)}: {orders_count}\n"
        f"🎁 {get_text('profile.referral_count', lang)}: {referrals_count}\n"
        f"⭐️ {get_text('profile.vip_status', lang)}: {vip_display}"
    )

    # Inline buttons
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ " + get_text("profile.setup", lang), callback_data="profile:setup")
    kb.button(text="📦 " + get_text("menu.my_purchases", lang), callback_data="menu:purchases")
    kb.button(text="💰 " + get_text("menu.wallet", lang), callback_data="menu:wallet")
    kb.button(text="🌐 " + get_text("menu.language", lang), callback_data="menu:language")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="menu:main")
    kb.button(text="✖️ " + get_text("common.close", lang), callback_data="profile:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        chat_id=message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )


@router.callback_query(F.data == "profile:show")
async def profile_show_callback(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    await show_profile(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "profile:close")
async def profile_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer("Closed")


# ---------- Profile editing ----------
@router.callback_query(F.data == "profile:setup")
async def setup_profile_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 " + get_text("profile.name", lang), callback_data="profile:edit_name")
    kb.button(text="🌐 " + get_text("menu.language", lang), callback_data="menu:language")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="profile:show")
    kb.button(text="✖️ " + get_text("common.close", lang), callback_data="profile:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        f"✏️ {get_text('profile.setup', lang)}\n\n{get_text('profile.edit_choice', lang)}",
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data == "profile:edit_phone")
async def edit_phone_placeholder(callback: CallbackQuery, lang="fa"):
    await callback.answer(get_text("profile.phone_not_supported", lang, default="Phone editing not available yet."), show_alert=True)


@router.callback_query(F.data == "profile:edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    prompt_msg = await MessageCleanupService.send_temporary(
        callback.message.chat.id,
        get_text("profile.enter_first_name", lang)
    )
    await state.update_data(prompt_msg_id=prompt_msg)
    await state.set_state(ProfileStates.FIRST_NAME)
    await callback.answer()


@router.message(ProfileStates.FIRST_NAME)
async def profile_first_name(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(first_name=message.text.strip())
    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    if prompt_id:
        await MessageCleanupService.delete_message(message.chat.id, prompt_id)
    await message.delete()

    prompt_msg = await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("profile.enter_last_name", lang)
    )
    await state.update_data(prompt_msg_id=prompt_msg)
    await state.set_state(ProfileStates.LAST_NAME)


@router.message(ProfileStates.LAST_NAME)
async def profile_last_name(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(last_name=message.text.strip())
    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    if prompt_id:
        await MessageCleanupService.delete_message(message.chat.id, prompt_id)
    await message.delete()

    prompt_msg = await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("profile.enter_phone", lang)
    )
    await state.update_data(prompt_msg_id=prompt_msg)
    await state.set_state(ProfileStates.PHONE)


@router.message(ProfileStates.PHONE)
async def profile_phone(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    phone = message.text.strip()
    if not phone:
        await message.answer(get_text("profile.invalid_phone", lang))
        return

    data = await state.get_data()
    prompt_id = data.get("prompt_msg_id")
    if prompt_id:
        await MessageCleanupService.delete_message(message.chat.id, prompt_id)
    await message.delete()

    user_repo = UserRepository(session)
    await user_repo.update_profile(
        db_user.id,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        phone=phone
    )
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("profile.saved", lang)
    )
    await state.clear()
