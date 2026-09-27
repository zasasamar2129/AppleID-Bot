from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.sql import and_

from app.database.models.enums import InventoryStatus, OrderStatus, OrderType
from app.database.models.inventory import Inventory
from app.database.models.order import Order
from app.database.session import async_session
from app.workers.job_runner import scheduled_job

logger = logging.getLogger(__name__)


@scheduled_job("process_orders", criticality="critical", slow_threshold=5.0, lock_ttl=90)
async def process_paid_orders_job() -> int:
    """Fulfil PAID ready-made orders by atomically claiming inventory.

    Idempotency: inventory claim and order transition are both conditional
    UPDATEs, so a duplicate or overlapping run matches 0 rows and can never
    deliver the same Apple ID twice. ``SKIP LOCKED`` stops concurrent runs from
    contending for the same rows.
    """
    processed = 0
    async with async_session() as session:
        stmt = (
            select(Order)
            .where(
                and_(
                    Order.status == OrderStatus.PAID,
                    Order.order_type == OrderType.READY_MADE,
                    Order.product_id.isnot(None),
                    Order.inventory_id.is_(None),
                )
            )
            .order_by(Order.created_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        orders = result.scalars().all()

        for order in orders:
            now = datetime.utcnow()

            # Atomically claim one AVAILABLE unit. The WHERE clause is the
            # concurrency guard: a parallel worker cannot match the same row.
            claimed = await session.execute(
                update(Inventory)
                .where(
                    and_(
                        Inventory.product_id == order.product_id,
                        Inventory.status == InventoryStatus.AVAILABLE,
                    )
                )
                .values(status=InventoryStatus.SOLD, sold_at=now, updated_at=now)
                .order_by(Inventory.created_at)
                .limit(1)
                .returning(Inventory.id)
            )
            inventory_id = claimed.scalar_one_or_none()

            if inventory_id is None:
                # Out of stock. Move to PROCESSING so we stop re-selecting it;
                # an admin restocks and can then fulfil it.
                await session.execute(
                    update(Order)
                    .where(and_(Order.id == order.id, Order.status == OrderStatus.PAID))
                    .values(status=OrderStatus.PROCESSING, updated_at=now)
                )
                logger.info("No inventory available for order %s", order.id)
                continue

            # Attach the claimed unit, still guarded on current status so a
            # concurrent run cannot overwrite it.
            attached = await session.execute(
                update(Order)
                .where(
                    and_(
                        Order.id == order.id,
                        Order.status == OrderStatus.PAID,
                        Order.inventory_id.is_(None),
                    )
                )
                .values(
                    inventory_id=inventory_id,
                    status=OrderStatus.FULFILLED,
                    updated_at=now,
                )
            )

            if attached.rowcount == 0:
                # Lost the race. Return the unit so it is not silently lost.
                await session.execute(
                    update(Inventory)
                    .where(
                        and_(
                            Inventory.id == inventory_id,
                            Inventory.status == InventoryStatus.SOLD,
                        )
                    )
                    .values(status=InventoryStatus.AVAILABLE, sold_at=None)
                )
                continue

            processed += 1
            logger.info("Fulfilled order %s with inventory %s", order.id, inventory_id)

        await session.commit()

    return processed
