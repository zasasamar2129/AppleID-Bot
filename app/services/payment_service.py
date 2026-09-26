from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.database.models.payment import Payment
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.payments.base import PaymentProvider
from app.payments.custom_api import CustomPaymentAPI

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, session: AsyncSession, provider: PaymentProvider | None = None):
        self.session = session
        self.payment_repo = PaymentRepository(session)
        self.order_repo = OrderRepository(session)
        self.wallet_repo = WalletRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.provider = provider if provider else CustomPaymentAPI()

    async def create_payment(self, order_id: int, user_id: int, method: PaymentMethod, amount: Decimal, currency: str = "IRR") -> Payment:
        data = {
            "order_id": order_id,
            "user_id": user_id,
            "method": method,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.PENDING,
        }
        payment = await self.payment_repo.create(data)
        return payment

    async def create_online_payment(self, order: Order, user_id: int) -> Payment | None:
        if not settings.is_online_payment_configured:
            logger.error("Online payment not configured")
            return None
        payment = await self.create_payment(order.id, user_id, PaymentMethod.ONLINE, order.final_price)
        # In real implementation, call provider to get external ID and URL
        # For now, we leave it as pending and the worker will handle
        return payment

    async def verify_online_payment(self, payment: Payment) -> bool:
        # Check with provider
        try:
            result = await self.provider.verify_payment(payment)
            if result.get("paid"):
                await self.mark_payment_paid(payment.id, external_id=result.get("external_id"))
                return True
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
        return False

    async def mark_payment_paid(self, payment_id: int, external_id: str | None = None) -> Payment | None:
        payment = await self.payment_repo.update_status(payment_id, PaymentStatus.PAID, {"external_payment_id": external_id})
        if payment:
            # Update order status to PAID
            order = await self.order_repo.get_by_id(payment.order_id)
            if order and order.status == OrderStatus.PENDING_PAYMENT:
                await self.order_repo.update_status(order.id, OrderStatus.PAID, {"paid_at": datetime.utcnow()})
        return payment

    async def process_wallet_payment(self, order: Order, user_id: int) -> bool:
        # Check wallet balance and deduct
        wallet = await self.wallet_repo.get_or_create(user_id)
        if wallet.balance < order.final_price:
            return False
        # Begin transaction: deduct, create ledger, mark order paid
        wallet.balance -= order.final_price
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)
        from app.database.models.enums import WalletTransactionType
        await self.wallet_repo.add_transaction(wallet.id, WalletTransactionType.PURCHASE, -order.final_price, wallet.balance, reference_id=str(order.id), description=f"Purchase order {order.id}")
        await self.order_repo.update_status(order.id, OrderStatus.PAID, {"paid_at": datetime.utcnow(), "payment_method": PaymentMethod.WALLET})
        return True

    async def create_card_payment(self, order: Order, user_id: int, card_number: str, holder: str, bank: str) -> Payment:
        payment = await self.create_payment(order.id, user_id, PaymentMethod.CARD_TO_CARD, order.final_price)
        payment.status = PaymentStatus.WAITING_USER
        await self.session.commit()
        return payment

    async def submit_card_receipt(self, payment_id: int, receipt_file_id: str, reference: str | None = None) -> Payment | None:
        payment = await self.payment_repo.update_status(payment_id, PaymentStatus.PENDING_VERIFICATION, {"receipt_file_id": receipt_file_id, "transaction_id": reference})
        return payment

    async def approve_card_payment(self, payment_id: int, admin_id: int) -> Payment | None:
        payment = await self.payment_repo.update_status(payment_id, PaymentStatus.PAID)
        if payment:
            order = await self.order_repo.get_by_id(payment.order_id)
            if order and order.status == OrderStatus.PENDING_PAYMENT:
                await self.order_repo.update_status(order.id, OrderStatus.PAID, {"paid_at": datetime.utcnow()})
        return payment

    async def reject_card_payment(self, payment_id: int, admin_id: int) -> Payment | None:
        payment = await self.payment_repo.update_status(payment_id, PaymentStatus.FAILED)
        if payment:
            order = await self.order_repo.get_by_id(payment.order_id)
            if order and order.status in [OrderStatus.PENDING_PAYMENT, OrderStatus.PAID]:
                # If already paid, need refund? For simplicity, set cancelled
                if order.status == OrderStatus.PAID:
                    await self.order_repo.update_status(order.id, OrderStatus.CANCELLED, {"cancelled_at": datetime.utcnow()})
                else:
                    await self.order_repo.update_status(order.id, OrderStatus.CANCELLED, {"cancelled_at": datetime.utcnow()})
        return payment
