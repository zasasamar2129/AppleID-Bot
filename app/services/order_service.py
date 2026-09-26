from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import OrderStatus, OrderType, PaymentMethod
from app.database.models.order import Order
from app.database.repositories.coupon_repo import CouponRepository
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.services.coupon_service import CouponService
from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.wallet_repo = WalletRepository(session)
        self.user_repo = UserRepository(session)
        self.coupon_repo = CouponRepository(session)
        self.inventory_service = InventoryService(session)
        self.coupon_service = CouponService(session)

    async def create_order(
        self,
        user_id: int,
        product_id: int | None,
        order_type: OrderType,
        price: Decimal,
        discount: Decimal = Decimal("0"),
        final_price: Decimal | None = None,
        currency: str = "IRR",
        customer_information: dict | None = None,
        inventory_id: int | None = None,
        payment_method: PaymentMethod | None = None,
    ) -> Order:
        if final_price is None:
            final_price = price - discount
        data = {
            "user_id": user_id,
            "product_id": product_id,
            "inventory_id": inventory_id,
            "order_type": order_type,
            "price": price,
            "discount": discount,
            "final_price": final_price,
            "currency": currency,
            "payment_method": payment_method,
            "status": OrderStatus.PENDING_PAYMENT,
            "customer_information": json.dumps(customer_information) if customer_information else None,
        }
        order = await self.order_repo.create(data)
        return order

    async def update_status(self, order_id: int, new_status: OrderStatus, extra: dict | None = None) -> Order | None:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            return None
        if not self._is_valid_transition(order.status, new_status):
            logger.warning(f"Invalid order status transition from {order.status} to {new_status} for order {order_id}")
            return None
        return await self.order_repo.update_status(order_id, new_status, extra)

    def _is_valid_transition(self, current: OrderStatus, new: OrderStatus) -> bool:
        valid_transitions = {
            OrderStatus.PENDING_PAYMENT: [OrderStatus.PAID, OrderStatus.CANCELLED, OrderStatus.EXPIRED],
            OrderStatus.PAID: [OrderStatus.PROCESSING, OrderStatus.FULFILLED, OrderStatus.CANCELLED, OrderStatus.REFUND_PENDING],
            OrderStatus.PROCESSING: [OrderStatus.FULFILLED, OrderStatus.CANCELLED],
            OrderStatus.FULFILLED: [OrderStatus.DELIVERED, OrderStatus.CANCELLED],
            OrderStatus.DELIVERED: [],
            OrderStatus.CANCELLED: [],
            OrderStatus.REFUND_PENDING: [OrderStatus.REFUNDED],
            OrderStatus.REFUNDED: [],
            OrderStatus.DISPUTED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
        }
        return new in valid_transitions.get(current, [])

    async def assign_inventory_to_order(self, order_id: int, inventory_id: int) -> None:
        order = await self.order_repo.get_by_id(order_id)
        if order and not order.inventory_id:
            order.inventory_id = inventory_id
            await self.session.commit()

    async def cancel_order(self, order_id: int) -> bool:
        order = await self.order_repo.get_by_id(order_id)
        if not order or order.status not in [OrderStatus.PENDING_PAYMENT, OrderStatus.PAID]:
            return False
        if order.inventory_id:
            await self.inventory_repo.release_reservation(order.inventory_id)
        await self.order_repo.update_status(order_id, OrderStatus.CANCELLED, {"cancelled_at": datetime.utcnow()})
        return True

    async def get_user_orders(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Order]:
        return await self.order_repo.get_by_user(user_id, limit, offset)

    async def get_order(self, order_id: int) -> Order | None:
        return await self.order_repo.get_by_id(order_id)

    async def process_wallet_payment(self, order: Order, user_id: int) -> bool:
        """Deduct wallet balance and mark order paid."""
        wallet = await self.wallet_repo.get_or_create(user_id)
        if wallet.balance < order.final_price:
            return False

        wallet.balance -= order.final_price
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)

        from app.database.models.enums import WalletTransactionType
        await self.wallet_repo.add_transaction(
            wallet.id,
            WalletTransactionType.PURCHASE,
            -order.final_price,
            wallet.balance,
            reference_id=str(order.id),
            description=f"Purchase order {order.id}"
        )

        await self.order_repo.update_status(
            order.id,
            OrderStatus.PAID,
            {"paid_at": datetime.utcnow(), "payment_method": PaymentMethod.WALLET}
        )
        return True
