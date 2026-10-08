from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import button
from app.config import settings
from app.database.models.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.localization import get_text
from app.services.coupon_service import CouponService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentError, PaymentService
from app.services.settings_service import SettingsService
from app.states.payment import CardToCardStates
from app.states.purchase import PurchaseStates
from app.utils.formatting import format_price, generate_tracking_id
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def is_payment_method_enabled(session: AsyncSession, enable_key: str) -> bool:
    """Check a payment method's admin toggle. Defaults to enabled."""
    settings_service = SettingsService(session)
    methods = await settings_service.get_payment_methods()
    return bool(methods.get(enable_key, True))


async def _get_order_for_payment(session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        return None, None
    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    return order_id, order


async def render_payment_screen(
    target,
    state: FSMContext,
    session: AsyncSession,
    lang: str,
    coupon_applied: str | None = None,
) -> None:
    """Show the payment method screen (used after coupon apply / skip / back)."""
    from aiogram.types import CallbackQuery, Message
    from app.handlers.products import build_payment_keyboard
    from app.services.product_service import ProductService

    order_id, order = await _get_order_for_payment(session, state)
    if not order:
        if isinstance(target, CallbackQuery):
            await target.answer(get_text("errors.order_not_found", lang), show_alert=True)
        return

    # Resolve the chat: CallbackQuery -> .message, Message -> itself.
    chat_id = target.message.chat.id if isinstance(target, CallbackQuery) else target.chat.id

    product_service = ProductService(session)
    product = await product_service.get_product(order.product_id) if order.product_id else None

    lines = []
    if product:
        lines.append(get_text("products.product_name", lang, name=product.name))
    lines.append(get_text("products.final_price", lang, final_price=format_price(order.final_price, lang)))
    if coupon_applied:
        lines.append(coupon_applied)
    if product and product.description:
        lines.append(product.description)
    text = "\n".join(lines)

    kb = await build_payment_keyboard(session, lang)
    await MessageCleanupService.show_screen(
        chat_id=chat_id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await state.set_state(PurchaseStates.SELECT_PAYMENT)
    if isinstance(target, CallbackQuery):
        await target.answer()


@router.callback_query(F.data == "purchase:coupon")
async def coupon_prompt(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    _, order = await _get_order_for_payment(session, state)
    if not order:
        await callback.answer(get_text("errors.order_not_found", lang), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("coupon.skip", lang), callback_data="purchase:coupon_skip", emoji_key="cancel", lang=lang))
    kb.adjust(1)
    await callback.message.edit_text(get_text("coupon.prompt", lang), reply_markup=kb.as_markup())
    await state.set_state(PurchaseStates.SELECT_COUPON)
    await callback.answer()


@router.callback_query(F.data == "purchase:coupon_skip")
async def coupon_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    await render_payment_screen(callback, state, session, lang)


@router.message(PurchaseStates.SELECT_COUPON, F.text)
async def coupon_apply(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    try:
        await message.delete()
    except Exception:
        pass
    code = message.text.strip().upper()
    _, order = await _get_order_for_payment(session, state)
    if not order:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return

    coupon_service = CouponService(session)
    coupon = await coupon_service.validate_coupon(
        code,
        user_id=db_user.id,
        order_amount=order.final_price,
        product_id=order.product_id,
    )
    if not coupon:
        await message.answer(get_text("coupon.invalid_for_order", lang))
        return

    discount = await coupon_service.calculate_discount(coupon, order.final_price)
    order.final_price = max(order.final_price - discount, 0)
    await coupon_service.apply_coupon(coupon, db_user.id, order.id)
    await session.commit()

    applied_text = get_text("coupon.applied", lang, code=coupon.code, discount=format_price(discount, lang))
    await render_payment_screen(message, state, session, lang, coupon_applied=applied_text)


def _receipt_done_text(order, lang: str, reference: str | None = None) -> str:
    """Return the message shown after a receipt is submitted.

    For Personal Apple ID orders the customer is told that the admin has been
    notified and will contact them soon.
    """
    if order and order.order_type.value == "PERSONAL":
        return get_text("payment.receipt_submitted_personal", lang)
    if reference:
        return get_text("payment.reference_received", lang, reference=reference)
    return get_text("payment.receipt_received", lang)


@router.callback_query(F.data == "pay:online")
async def online_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await callback.answer(get_text("errors.order_not_found", lang), show_alert=True)
        return
    if not settings.is_online_payment_configured or not await is_payment_method_enabled(session, "payment_online_enabled"):
        await callback.answer(get_text("payment.gateway_unavailable", lang), show_alert=True)
        return

    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer(get_text("errors.not_found", lang), show_alert=True)
        return

    # Idempotency: never let a user mint attempt A/B/C for one order.
    if order.status == OrderStatus.PAID:
        await callback.answer(get_text("payment.already_paid", lang), show_alert=True)
        return

    payment_service = PaymentService(session)
    existing = await payment_service.find_open_online_payment(db_user.id, order.id)
    if existing:
        if existing.authority and existing.status == PaymentStatus.PENDING_VERIFICATION:
            # A token is already out there — re-offer it instead of burning a
            # second attempt the user did not ask for.
            gateway_data = {"url": settings.sep_payment_url or "", "token": existing.authority}
            await _send_gateway_button(callback, existing, gateway_data, order, lang)
            await callback.answer()
            return
        await callback.answer(get_text("payment.already_pending", lang), show_alert=True)
        return

    try:
        payment, gateway_data = await payment_service.create_online_payment(
            user_id=db_user.id,
            amount_toman=order.final_price,
            order_id=order.id,
            currency=order.currency,
        )
    except PaymentError as exc:
        await callback.message.edit_text(get_text("payment.gateway_unavailable", lang))
        await state.clear()
        await callback.answer()
        logger.warning("online payment refused for order=%s: %s", order.id, exc)
        return

    await _send_gateway_button(callback, payment, gateway_data, order, lang)
    await state.clear()
    await callback.answer()


async def _send_gateway_button(callback, payment, gateway_data, order, lang) -> None:
    """Show the pay button. Opening the bank page needs no server of ours."""
    token = gateway_data.get("token") or payment.authority
    base_url = gateway_data.get("url") or settings.sep_payment_url
    kb = InlineKeyboardBuilder()
    if token and base_url:
        # SEP accepts the token as a query parameter on its payment page.
        sep_url = f"{base_url}?Token={token}&GetMethod=true"
        kb.button(text=get_text("payment.pay_button", lang), url=sep_url)
    kb.button(text=get_text("common.cancel", lang), callback_data="menu:main")
    kb.adjust(1)

    text = (
        f"💳 {get_text('payment.online_title', lang)}\n\n"
        f"🧾 {get_text('orders.order', lang, order_id=order.id)}\n"
        f"💰 {get_text('payment.amount_due', lang, amount=format_price(order.final_price, lang))}\n"
        f"🏦 {get_text('payment.bank', lang)}: {get_text('payment.saman_bank', lang)}\n\n"
        f"{get_text('payment.online_instruction', lang)}"
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "pay:wallet")
async def wallet_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    if not await is_payment_method_enabled(session, "payment_wallet_enabled"):
        await callback.answer(get_text("errors.payment_unavailable", lang), show_alert=True)
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await callback.answer(get_text("errors.order_not_found", lang), show_alert=True)
        return

    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer(get_text("errors.not_found", lang), show_alert=True)
        return

    # Idempotency guard: only a PENDING_PAYMENT order can be paid via wallet.
    if order.status != OrderStatus.PENDING_PAYMENT:
        await callback.answer(get_text("payment.already_submitted", lang), show_alert=True)
        return

    wallet_repo = WalletRepository(session)
    wallet = await wallet_repo.get_or_create(db_user.id)
    if wallet.balance < order.final_price:
        await callback.answer(get_text("wallet.insufficient_balance", lang), show_alert=True)
        return

    order_service = OrderService(session)
    success = await order_service.process_wallet_payment(order, db_user.id)
    if not success:
        await callback.answer(get_text("wallet.insufficient_balance", lang), show_alert=True)
        return

    if order.order_type.value == "ready_made":
        # Only fulfill if there's an inventory assignment for THIS order; never grab an
        # arbitrary available row that might already be reserved/sold for another order.
        inventory_service = InventoryService(session)
        inventory = None
        if order.inventory_id:
            inventory = await inventory_service.get_by_id(order.inventory_id)
        if inventory and inventory.status.value == "RESERVED":
            await inventory_service.mark_sold(inventory.id)
            order.inventory_id = inventory.id
            await order_service.update_status(order.id, OrderStatus.FULFILLED)
            account = await inventory_service.decrypt_inventory(inventory)
            fulfillment = await inventory_service.get_fulfillment_data(inventory)
            # NOTE: order.user is the ORM User record, and order.user.telegram_id is the actual Telegram chat ID
            delivery_text = (
                f"🎉 Purchase Completed\n\nOrder #{order.id}\n\n🍏 Apple ID\n"
                f"📧 {account.get('email')}\n🔑 Password: {account.get('password')}\n"
                "\n\n⚠️ <b>مهم: Find My iPhone را خاموش کنید.</b>\n"
                "<b>⚠️ Important: Turn off Find My iPhone.</b>"
            )
            await callback.bot.send_message(
                chat_id=order.user.telegram_id,
                text=delivery_text,
                parse_mode="HTML",
            )
            await order_service.update_status(order.id, OrderStatus.DELIVERED)
    elif order.order_type.value == "personal":
        # Personal Apple ID: paid but no auto-delivery. An admin contacts the
        # customer to arrange delivery of the personal Apple ID manually.
        await callback.bot.send_message(
            chat_id=order.user.telegram_id,
            text=get_text("payment.personal_paid", lang),
        )

    await callback.message.edit_text(get_text("payment.success", lang))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "pay:card")
async def choose_card_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    if not await is_payment_method_enabled(session, "payment_card_enabled"):
        await callback.answer(get_text("errors.payment_unavailable", lang), show_alert=True)
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await callback.answer(get_text("errors.order_not_found", lang), show_alert=True)
        return

    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer(get_text("errors.not_found", lang), show_alert=True)
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_order(order_id)
    if not payment:
        tracking_id = generate_tracking_id()
        payment = await payment_repo.create({
            "order_id": order_id,
            "user_id": db_user.id,
            "method": PaymentMethod.CARD_TO_CARD,
            "amount": order.final_price,
            "currency": order.currency,
            "external_payment_id": tracking_id,
            "status": PaymentStatus.PENDING,
        })
    else:
        payment.method = PaymentMethod.CARD_TO_CARD
        # Re-issue a tracking ID if the payment has none yet.
        if not payment.external_payment_id:
            payment.external_payment_id = generate_tracking_id()
        await session.commit()
    tracking_id = payment.external_payment_id or "—"

    card_number = settings.card_to_card_number or "Not configured"
    card_holder = settings.card_to_card_holder or "Not configured"
    bank = settings.card_to_card_bank or "Not configured"
    amount_display = format_price(order.final_price, lang)

    text = (
        f"💳 {get_text('payment.card_title', lang)}\n\n"
        f"🧾 {get_text('orders.order', lang, order_id=order.id)}\n"
        f"🆔 {get_text('payment.tracking_id', lang)}: {tracking_id}\n\n"
        f"💰 {get_text('payment.amount_due', lang, amount=amount_display)}\n"
        f"🏦 {get_text('payment.bank', lang)}: {bank}\n"
        f"💳 {get_text('payment.card_number', lang)}: {card_number}\n"
        f"👤 {get_text('payment.card_holder', lang)}: {card_holder}\n\n"
        f"{get_text('payment.card_instruction', lang)}\n"
        f"{get_text('payment.card_instruction_2', lang)}"
    )
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("payment.card_pay_confirm", lang), callback_data="card:confirm", style="success", emoji_key="success", lang=lang))
    kb.add(button(get_text("common.back", lang), callback_data="purchase:back", emoji_key="back", lang=lang))
    kb.add(button(get_text("common.cancel", lang), callback_data="menu:main", style="danger", emoji_key="cancel", lang=lang))
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await state.set_state(CardToCardStates.SHOW_INSTRUCTIONS)
    await callback.answer()


@router.callback_query(CardToCardStates.SHOW_INSTRUCTIONS, F.data == "card:confirm")
async def confirm_payment(callback: CallbackQuery, state: FSMContext, lang="fa"):
    text = get_text("payment.proof_prompt", lang)
    kb = InlineKeyboardBuilder()
    kb.add(button(get_text("payment.send_photo", lang), callback_data="card:photo", emoji_key="receipt", lang=lang))
    kb.add(button(get_text("payment.send_text", lang), callback_data="card:text", emoji_key="reference", lang=lang))
    kb.add(button(get_text("common.back", lang), callback_data="card:back_to_instructions", emoji_key="back", lang=lang))
    kb.add(button(get_text("common.cancel", lang), callback_data="menu:main", style="danger", emoji_key="cancel", lang=lang))
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await state.set_state(CardToCardStates.WAITING_FOR_RECEIPT)
    await callback.answer()


@router.callback_query(CardToCardStates.WAITING_FOR_RECEIPT, F.data == "card:photo")
async def request_photo(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.send_temporary(callback.message.chat.id, get_text("payment.send_photo_prompt", lang))
    await callback.answer()


@router.callback_query(CardToCardStates.WAITING_FOR_RECEIPT, F.data == "card:text")
async def request_text(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await MessageCleanupService.send_temporary(callback.message.chat.id, get_text("payment.send_text_prompt", lang))
    await callback.answer()


@router.callback_query(CardToCardStates.WAITING_FOR_RECEIPT, F.data == "card:back_to_instructions")
async def back_to_instructions(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    await choose_card_payment(callback, state, session, db_user, lang)


@router.message(CardToCardStates.WAITING_FOR_RECEIPT, F.content_type.in_([ContentType.PHOTO, ContentType.DOCUMENT]))
async def handle_photo_receipt(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.answer(get_text("payment.invalid_receipt", lang))
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_order(order_id)
    if not payment or payment.status != PaymentStatus.PENDING:
        await message.answer(get_text("payment.already_submitted", lang))
        await state.clear()
        return

    # If the image came in as a Document, store it as a document so the admin
    # can re-display it with the correct API call (photo vs document).
    is_photo = bool(message.photo)
    payment.receipt_file_id = file_id
    payment.receipt_type = "photo" if is_photo else "document"
    payment.status = PaymentStatus.PENDING_VERIFICATION
    await session.commit()

    notifier = NotificationService(message.bot)
    await notifier.notify_admins_new_payment(payment)

    # Receipt confirmation is a business record — protected, never auto-deleted.
    _, order = await _get_order_for_payment(session, state)
    text = _receipt_done_text(order, lang)
    await MessageCleanupService.show_screen(
        message.chat.id,
        text,
        protected=True,
    )
    await state.clear()


@router.message(CardToCardStates.WAITING_FOR_RECEIPT, F.text)
async def handle_text_receipt(message: Message, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    text = message.text.strip()
    if len(text) < 3 or not re.match(r"^[a-zA-Z0-9\-_]+$", text):
        await message.answer(get_text("payment.invalid_receipt", lang))
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer(get_text("errors.order_not_found", lang))
        await state.clear()
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_order(order_id)
    if not payment or payment.status != PaymentStatus.PENDING:
        await message.answer(get_text("payment.already_submitted", lang))
        await state.clear()
        return

    payment.transaction_id = text
    payment.receipt_type = "text"
    payment.status = PaymentStatus.PENDING_VERIFICATION
    await session.commit()

    notifier = NotificationService(message.bot)
    await notifier.notify_admins_new_payment(payment)

    # Reference confirmation is a business record — protected, never auto-deleted.
    _, order = await _get_order_for_payment(session, state)
    text = _receipt_done_text(order, lang, reference=text)
    await MessageCleanupService.show_screen(
        message.chat.id,
        text,
        protected=True,
    )
    await state.clear()
