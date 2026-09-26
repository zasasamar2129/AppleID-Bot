from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.enums import OrderStatus, PaymentStatus
from app.database.repositories.admin_repo import AdminRepository
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.user_repo import UserRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.states.admin.payment import AdminPaymentStates
from app.utils.formatting import format_price

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:payments")
async def payments_menu(callback: CallbackQuery, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text="🟡 Pending Verification", callback_data="admin:payments:pending")
    kb.button(text="✅ Approved", callback_data="admin:payments:approved")
    kb.button(text="❌ Rejected", callback_data="admin:payments:rejected")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text("💳 Payments", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:payments:pending")
async def pending_payments(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    payment_repo = PaymentRepository(session)
    payments = await payment_repo.get_pending_verification()
    if not payments:
        await callback.message.edit_text("✅ No pending payments.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for p in payments:
        kb.button(text=f"Payment {p.id} - Order {p.order_id}", callback_data=f"admin:payment:{p.id}")
    kb.button(text="⬅️ Back", callback_data="admin:payments")
    kb.adjust(1)
    await callback.message.edit_text("🟡 Pending Verification", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:payments:approved")
async def approved_payments(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    payment_repo = PaymentRepository(session)
    payments = await payment_repo.get_all(status=PaymentStatus.PAID, limit=50)
    if not payments:
        await callback.message.edit_text("✅ No approved payments.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for p in payments:
        kb.button(text=f"Payment {p.id} - Order {p.order_id}", callback_data=f"admin:payment:{p.id}")
    kb.button(text="⬅️ Back", callback_data="admin:payments")
    kb.adjust(1)
    await callback.message.edit_text("✅ Approved Payments", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:payments:rejected")
async def rejected_payments(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    payment_repo = PaymentRepository(session)
    payments = await payment_repo.get_all(status=PaymentStatus.FAILED, limit=50)
    if not payments:
        await callback.message.edit_text("❌ No rejected payments.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for p in payments:
        kb.button(text=f"Payment {p.id} - Order {p.order_id}", callback_data=f"admin:payment:{p.id}")
    kb.button(text="⬅️ Back", callback_data="admin:payments")
    kb.adjust(1)
    await callback.message.edit_text("❌ Rejected Payments", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:payment:"))
async def payment_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    payment_id = int(callback.data.split(":")[2])
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment:
        await callback.answer("Payment not found", show_alert=True)
        return

    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(payment.order_id) if payment.order_id else None
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(payment.user_id)

    amount_str = format_price(payment.amount, lang)
    order_label = f"#{order.id}" if order else "Wallet top-up"
    user_label = f"{user.first_name} {user.last_name or ''}" if user else "—"
    product_label = (order.product.name if order and order.product else "Personal Apple ID") if order else "—"
    text = (
        f"💳 Payment Verification\n\n"
        f"Payment ID: {payment.id}\n"
        f"Order: {order_label}\n"
        f"Product: {product_label}\n"
        f"User: {user_label}\n"
        f"Telegram ID: {user.telegram_id if user else '—'}\n"
        f"Amount: {amount_str}\n"
        f"Method: Card-to-Card\n"
        f"Tracking ID: {payment.external_payment_id or '—'}\n"
        f"Reference: {payment.transaction_id or '—'}\n"
        f"Receipt Type: {payment.receipt_type or '—'}\n"
        f"Status: {payment.status.value}\n"
    )

    # Show the customer-entered information from the order (name, email, phone).
    if order and order.customer_information:
        text += "\n👤 Customer Info:\n"
        try:
            import json as _json
            info = _json.loads(order.customer_information) if isinstance(order.customer_information, str) else order.customer_information
        except (ValueError, TypeError):
            info = {}
        for key, value in info.items():
            if value:
                text += f"  {key}: {value}\n"
    kb = InlineKeyboardBuilder()
    if payment.receipt_file_id:
        kb.button(text="📎 View Receipt", callback_data=f"admin:viewreceipt:{payment.id}")
    if payment.status == PaymentStatus.PENDING_VERIFICATION:
        kb.button(text="✅ Approve", callback_data=f"admin:approve:{payment.id}")
        kb.button(text="❌ Reject", callback_data=f"admin:reject:{payment.id}")
    kb.button(text="⬅️ Back", callback_data="admin:payments:pending")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:viewreceipt:"))
async def view_receipt(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    payment_id = int(callback.data.split(":")[2])
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment or not payment.receipt_file_id:
        await callback.answer(get_text("admin.payments.receipt_not_found", lang), show_alert=True)
        return
    try:
        if payment.receipt_type == "photo":
            try:
                await callback.message.answer_photo(photo=payment.receipt_file_id)
            except Exception:
                # File type mismatch (e.g. legacy rows / document-type image).
                await callback.message.answer_document(document=payment.receipt_file_id)
        else:
            await callback.message.answer_document(document=payment.receipt_file_id)
    except Exception as e:
        logger.error(f"Could not display receipt for payment {payment.id}: {e}")
        await callback.message.answer(get_text("admin.payments.invalid_receipt", lang))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:approve:"))
async def approve_payment(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    """Approve a pending payment and fulfill the associated order.

    This operation is designed to be idempotent and safe to run twice:
    a second call sees the payment already PAID (or the order not in a
    payable state) and short-circuits without re-fulfilling anything.
    """
    payment_id = int(callback.data.split(":")[2])
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment or payment.status != PaymentStatus.PENDING_VERIFICATION:
        await callback.answer("Payment already processed or invalid", show_alert=True)
        return

    order_service = OrderService(session)
    inventory_service = InventoryService(session)
    order = await order_service.get_order(payment.order_id) if payment.order_id else None
    if order and order.user_id != payment.user_id:
        await callback.answer("Payment/order mismatch", show_alert=True)
        return
    if order and order.status != OrderStatus.PENDING_PAYMENT:
        await callback.answer("Order is not in payable state", show_alert=True)
        return

    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by_telegram_id(callback.from_user.id)
    if not admin:
        await callback.answer("Admin record not found. Please contact super admin.", show_alert=True)
        return

    # --- Idempotency: guard so double approval cannot re-credit / re-fulfill ---
    # Use a DB-level conditional update to atomically claim the payment.
    from sqlalchemy import update as sa_update
    from sqlalchemy.sql import and_

    from app.database.models.payment import Payment

    claim = await session.execute(
        sa_update(Payment)
        .where(
            and_(
                Payment.id == payment.id,
                Payment.status == PaymentStatus.PENDING_VERIFICATION,
            )
        )
        .values(
            status=PaymentStatus.PAID,
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
        )
    )
    if claim.rowcount == 0:
        # Someone else approved it between our read and write.
        await callback.answer("Payment already processed", show_alert=True)
        return

    # For wallet top-up payments (no order), credit the user's wallet exactly once.
    if not order:
        from app.services.wallet_service import WalletService
        wallet_service = WalletService(session)
        await wallet_service.deposit(
            payment.user_id,
            payment.amount,
            reference_id=f"payment_{payment.id}",
            description="Wallet top-up (card-to-card)",
        )
    else:
        order.status = OrderStatus.PAID
        order.paid_at = datetime.utcnow()

        # Deliver Apple ID if ready-made and inventory already reserved
        if order.order_type.value == "READY_MADE":
            inventory = None
            if order.inventory_id:
                inventory = await inventory_service.get_by_id(order.inventory_id)
            else:
                # Fallback: try to get available inventory (should not happen)
                inventory = await inventory_service.get_available_for_product(order.product_id)

            if inventory and inventory.status.value == "RESERVED":
                await inventory_service.mark_sold(inventory.id)
                order.inventory_id = inventory.id
                order.status = OrderStatus.FULFILLED

                account = await inventory_service.decrypt_inventory(inventory)
                fulfillment = await inventory_service.get_fulfillment_data(inventory)

                # Build delivery message
                delivery_text = f"🎉 Purchase Completed\n\nOrder #{order.id}\n\n🍏 Apple ID\n"
                delivery_text += f"📧 {account.get('email', '—')}\n"
                delivery_text += f"🔑 Password: {account.get('password', '—')}\n"

                if fulfillment:
                    for key, value in fulfillment.items():
                        if key != "notes":
                            delivery_text += f"{key}: {value}\n"
                    notes = fulfillment.get("notes")
                    if notes:
                        delivery_text += f"📝 Notes: {notes}\n"

                # Important bold note after purchase
                delivery_text += (
                    "\n\n⚠️ <b>مهم: Find My iPhone را خاموش کنید.</b>\n"
                    "<b>⚠️ Important: Turn off Find My iPhone.</b>"
                )

                try:
                    await callback.bot.send_message(
                        chat_id=order.user.telegram_id,
                        text=delivery_text,
                        parse_mode="HTML",
                    )
                    order.status = OrderStatus.DELIVERED
                except Exception as e:
                    logger.error(f"Failed to send Apple ID for order {order.id}: {e}")
                    order.status = OrderStatus.FULFILLED
        elif order.order_type.value == "PERSONAL":
            # Personal Apple ID: paid. No auto-delivery — an admin contacts the
            # customer to arrange the personal Apple ID manually.
            try:
                await callback.bot.send_message(
                    chat_id=order.user.telegram_id,
                    text=get_text("payment.personal_paid", lang),
                )
            except Exception as e:
                logger.error(f"Failed to notify user for personal order {order.id}: {e}")

    await session.commit()

    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="approve_payment", target_type="payment", target_id=str(payment.id))

    # Notify the user using their Telegram ID (payment.user_id is a DB id).
    user = await UserRepository(session).get_by_id(payment.user_id)
    notifier = NotificationService(callback.bot)
    if user:
        try:
            await notifier.notify_user(user.telegram_id, "payment.approved", lang=user.language or "fa")
        except Exception:
            pass

    await callback.message.edit_text(f"✅ Payment {payment.id} approved.")
    await callback.answer("Approved", show_alert=True)


@router.callback_query(F.data.startswith("admin:reject:"))
async def reject_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    payment_id = int(callback.data.split(":")[2])
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment or payment.status != PaymentStatus.PENDING_VERIFICATION:
        await callback.answer("Payment already processed", show_alert=True)
        return

    await state.update_data(payment_id=payment_id)
    await callback.message.answer("Please enter rejection reason (or send /skip):")
    await state.set_state(AdminPaymentStates.REJECT_REASON)
    await callback.answer()


@router.message(AdminPaymentStates.REJECT_REASON)
async def reject_reason(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    reason = message.text.strip()
    data = await state.get_data()
    payment_id = data.get("payment_id")
    if not payment_id:
        await message.answer("Payment not found.")
        await state.clear()
        return

    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment or payment.status != PaymentStatus.PENDING_VERIFICATION:
        await message.answer("Payment already processed.")
        await state.clear()
        return

    payment.rejection_reason = reason
    payment.status = PaymentStatus.FAILED
    await session.commit()

    order_service = OrderService(session)
    order = await order_service.get_order(payment.order_id) if payment.order_id else None
    if order and order.status == OrderStatus.PENDING_PAYMENT:
        await order_service.cancel_order(order.id)

    audit = AuditService(session)
    await audit.log(admin_telegram_id=message.from_user.id, action="reject_payment", target_type="payment", target_id=str(payment.id), metadata={"reason": reason})

    # Notify the user using their Telegram ID (payment.user_id is a DB id).
    user = await UserRepository(session).get_by_id(payment.user_id)
    notifier = NotificationService(message.bot)
    if user:
        try:
            await notifier.notify_user(user.telegram_id, "payment.rejected", lang=user.language or "fa")
        except Exception:
            pass

    await message.answer(f"❌ Payment {payment.id} rejected.")
    await state.clear()
