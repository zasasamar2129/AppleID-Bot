from __future__ import annotations

import logging

from app.database.models.enums import OrderStatus, PaymentStatus
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.session import async_session

logger = logging.getLogger(__name__)


async def cleanup_expired_job():
    try:
        async with async_session() as session:
            inventory_repo = InventoryRepository(session)
            inventory_service = None
            expired_inv = await inventory_repo.get_expired_reservations()
            for inv in expired_inv:
                await inventory_repo.release_reservation(inv.id)
                logger.info(f"Released expired reservation for inventory {inv.id}")

            # Also expire old pending payments
            payment_repo = PaymentRepository(session)
            order_repo = OrderRepository(session)
            expired_payments = await payment_repo.get_expired_pending()
            for p in expired_payments:
                await payment_repo.update_status(p.id, PaymentStatus.EXPIRED)
                order = await order_repo.get_by_id(p.order_id)
                if order and order.status == OrderStatus.PENDING_PAYMENT:
                    await order_repo.update_status(order.id, OrderStatus.CANCELLED, {"cancelled_at": __import__("datetime").datetime.utcnow()})
                    # Release any inventory reserved for this order
                    if order.inventory_id:
                        inv = await inventory_repo.get_by_id(order.inventory_id)
                        if inv and inv.status.value == "RESERVED":
                            await inventory_repo.release_reservation(order.inventory_id)
                            logger.info(f"Released inventory {order.inventory_id} for expired order {order.id}")
            await session.commit()
    except Exception as e:
        logger.error(f"cleanup_expired_job failed: {e}", exc_info=True)
