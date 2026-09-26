from __future__ import annotations

import logging

from app.database.models.enums import OrderStatus
from app.database.repositories.order_repo import OrderRepository
from app.database.session import async_session
from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)


async def process_paid_orders_job():
    try:
        async with async_session() as session:
            order_repo = OrderRepository(session)
            # Find orders in PAID state that need processing
            from sqlalchemy import select

            from app.database.models.order import Order
            stmt = select(Order).where(Order.status == OrderStatus.PAID)
            result = await session.execute(stmt)
            paid_orders = result.scalars().all()
            for order in paid_orders:
                # For ready-made, assign inventory and fulfill
                if order.order_type.value == "ready_made":
                    inventory_service = InventoryService(session)
                    inv = await inventory_service.get_available_for_product(order.product_id)
                    if inv:
                        await order_repo.update_status(order.id, OrderStatus.PROCESSING)
                        # Assign the specific reserved/available inventory to this order
                        order.inventory_id = inv.id
                        await session.commit()
                        await inventory_service.mark_sold(inv.id)
                        await order_repo.update_status(order.id, OrderStatus.FULFILLED)
                        # Deliver data (decrypt and send) - would be in notification service
                        logger.info(f"Fulfilled order {order.id}")
                # For manual orders, no automatic inventory assignment
    except Exception as e:
        logger.error(f"process_paid_orders_job failed: {e}", exc_info=True)
