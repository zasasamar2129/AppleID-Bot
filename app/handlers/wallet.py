from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.repositories.payment_repo import PaymentRepository
from app.localization import get_text
from app.services.wallet_service import WalletService
from app.states.wallet import WalletTopUpStates
from app.utils.formatting import format_price, generate_tracking_id
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def show_wallet(message: Message, session: AsyncSession, db_user, lang="fa"):
    wallet_service = WalletService(session)
    balance = await wallet_service.get_balance(db_user.id)
    balance_str = format_price(balance, lang)

    text = f"💰 {get_text('wallet.title', lang)}\n\n{get_text('wallet.balance', lang, balance=balance_str)}"
    kb = InlineKeyboardBuilder()
    kb.button(text=f"➕ {get_text('wallet.top_up', lang)}", callback_data="wallet:topup")
    kb.button(text=f"📜 {get_text('wallet.history', lang)}", callback_data="wallet:history")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="wallet:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)


@router.callback_query(F.data == "wallet:show")
async def wallet_show_callback(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    await show_wallet(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        get_text("wallet.enter_amount", lang),
        reply_markup=None
    )
    await state.set_state(WalletTopUpStates.ENTER_AMOUNT)
    await callback.answer()


@router.message(WalletTopUpStates.ENTER_AMOUNT)
async def wallet_topup_amount(message: Message, state: FSMContext, lang="fa"):
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer(get_text("wallet.invalid_amount", lang))
        return
    # Store as string — FSM uses JSON (Redis) and Decimal is not serializable.
    await state.update_data(amount=str(amount))
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🌐 {get_text('payment.online', lang)}", callback_data="wallet_topup:online")
    kb.button(text=f"💳 {get_text('payment.card', lang)}", callback_data="wallet_topup:card")
    kb.button(text=f"❌ {get_text('common.cancel', lang)}", callback_data="wallet:close")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("wallet.select_method", lang),
        reply_markup=kb.as_markup()
    )
    await state.set_state(WalletTopUpStates.SELECT_METHOD)
    await message.delete()


@router.callback_query(WalletTopUpStates.SELECT_METHOD, F.data.startswith("wallet_topup:"))
async def wallet_topup_method(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    method = callback.data.split(":")[1]
    data = await state.get_data()
    amount = Decimal(data["amount"])  # stored as string (JSON-safe)

    if method == "online":
        if not settings.is_online_payment_configured:
            await callback.answer(get_text("payment.online_unavailable", lang), show_alert=True)
            await state.clear()
            return
        # Online payment would be handled here
        await callback.answer(get_text("payment.online_unavailable", lang), show_alert=True)
        await state.clear()
        return
    elif method == "card":
        card_number = settings.card_to_card_number or "Not configured"
        card_holder = settings.card_to_card_holder or "Not configured"
        bank = settings.card_to_card_bank or "Not configured"
        amount_str = format_price(amount, lang)
        tracking_id = generate_tracking_id()
        await state.update_data(tracking_id=tracking_id)  # JSON-safe string
        text = (
            f"💳 {get_text('wallet.card_title', lang)}\n\n"
            f"🆔 {get_text('payment.tracking_id', lang)}: {tracking_id}\n"
            f"💰 {get_text('wallet.amount', lang)}: {amount_str}\n"
            f"💳 {get_text('payment.card_number', lang)}: {card_number}\n"
            f"👤 {get_text('payment.card_holder', lang)}: {card_holder}\n"
            f"🏦 {get_text('payment.bank', lang)}: {bank}\n\n"
            f"{get_text('wallet.card_instruction', lang)}\n"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text=f"✅ {get_text('wallet.i_paid', lang)}", callback_data="wallet_topup:confirm_card")
        kb.button(text=f"❌ {get_text('common.cancel', lang)}", callback_data="wallet:close")
        kb.adjust(1)
        await MessageCleanupService.show_screen(callback.message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)
        await state.set_state(WalletTopUpStates.WAITING_CONFIRMATION)
        await callback.answer()


@router.callback_query(WalletTopUpStates.WAITING_CONFIRMATION, F.data == "wallet_topup:confirm_card")
async def wallet_topup_confirm_card(callback: CallbackQuery, state: FSMContext, lang="fa"):
    """Prompt user to send receipt photo or transaction reference"""
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📷 {get_text('payment.send_photo', lang)}", callback_data="wallet_topup:photo")
    kb.button(text=f"🔢 {get_text('payment.send_text', lang)}", callback_data="wallet_topup:text")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="wallet_topup:card")
    kb.button(text=f"❌ {get_text('common.cancel', lang)}", callback_data="wallet:close")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        get_text("payment.proof_prompt", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await state.set_state(WalletTopUpStates.WAITING_RECEIPT)
    await callback.answer()


@router.callback_query(WalletTopUpStates.WAITING_RECEIPT, F.data == "wallet_topup:photo")
async def wallet_topup_request_photo(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.send_temporary(callback.message.chat.id, get_text("payment.send_photo_prompt", lang))
    await callback.answer()


@router.callback_query(WalletTopUpStates.WAITING_RECEIPT, F.data == "wallet_topup:text")
async def wallet_topup_request_text(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.send_temporary(callback.message.chat.id, get_text("payment.send_text_prompt", lang))
    await callback.answer()


@router.callback_query(WalletTopUpStates.WAITING_RECEIPT, F.data == "wallet_topup:card")
async def wallet_topup_back_to_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    data = await state.get_data()
    amount = data["amount"]
    # Re-show card instructions
    await wallet_topup_method(callback, state, session, db_user, lang)


@router.message(WalletTopUpStates.WAITING_RECEIPT, F.content_type.in_([ContentType.PHOTO, ContentType.DOCUMENT]))
async def wallet_topup_handle_photo(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.answer(get_text("payment.invalid_receipt", lang))
        return

    data = await state.get_data()
    amount_str = data.get("amount")
    if not amount_str:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return
    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.create({
        "user_id": db_user.id,
        "method": "CARD_TO_CARD",
        "amount": amount,
        "currency": "IRR",
        "external_payment_id": data.get("tracking_id"),
        "status": "PENDING_VERIFICATION",
        "receipt_file_id": file_id,
        "receipt_type": "photo",
    })

    from app.services.notification_service import NotificationService
    notifier = NotificationService(message.bot)
    await notifier.notify_admins_new_payment(payment)

    # Receipt confirmation is a business record — send it through the tracker
    # as a protected message so later cleanup never removes it.
    sent = await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("payment.receipt_received", lang),
        protected=True,
    )
    await state.clear()
    return sent


@router.message(WalletTopUpStates.WAITING_RECEIPT, F.text)
async def wallet_topup_handle_text(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    text = message.text.strip()
    if len(text) < 3 or not text.replace("-", "").replace("_", "").isalnum():
        await message.answer(get_text("payment.invalid_receipt", lang))
        return

    data = await state.get_data()
    amount_str = data.get("amount")
    if not amount_str:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return
    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.create({
        "user_id": db_user.id,
        "method": "CARD_TO_CARD",
        "amount": amount,
        "currency": "IRR",
        "external_payment_id": data.get("tracking_id"),
        "status": "PENDING_VERIFICATION",
        "transaction_id": text,
        "receipt_type": "text",
    })

    from app.services.notification_service import NotificationService
    notifier = NotificationService(message.bot)
    await notifier.notify_admins_new_payment(payment)

    # Reference confirmation is a business record — protected, never auto-deleted.
    await MessageCleanupService.show_screen(
        message.chat.id,
        get_text("payment.reference_received", lang, reference=text),
        protected=True,
    )
    await state.clear()


@router.callback_query(F.data == "wallet:history")
async def wallet_history(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    wallet_service = WalletService(session)
    transactions = await wallet_service.get_transaction_history(db_user.id, limit=20)
    if not transactions:
        text = f"📜 {get_text('wallet.history', lang)}\n\n{get_text('wallet.empty_history', lang, default='No transactions yet.')}"
    else:
        text = f"📜 {get_text('wallet.history', lang)}\n\n"
        for txn in transactions:
            sign = "+" if txn.amount > 0 else ""
            text += f"{txn.created_at.strftime('%Y/%m/%d %H:%M')} | {sign}{format_price(txn.amount, lang)} | {txn.type.value}\n"
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="wallet:show")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="wallet:close")
    kb.adjust(1)
    await MessageCleanupService.show_screen(callback.message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)
    await callback.answer()


@router.callback_query(F.data == "wallet:close")
async def wallet_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer(get_text("common.closed", "fa"))
