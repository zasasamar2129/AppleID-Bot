from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.sql import and_

from app.database.models.enums import InventoryStatus, OrderStatus, PaymentStatus
from app.database.models.inventory import Inventory
from app.database.models.order import Order
from app.database.models.payment import Payment
from app.database.session import async_session
from app.workers.job_runner import scheduled_job

logger = logging.getLogger(__name__)

# A pending payment that nobody has completed after this long is abandoned.
PAYMENT_EXPIRY_MINUTES = 30

# Cap per run so cleanup cannot monopolise the event loop on a large backlog.
BATCH_SIZE = 200


@scheduled_job("cleanup_expired", criticality="low", slow_threshold=5.0, lock_ttl=90)
async def cleanup_expired_job() -> int:
    """Release expired reservations and expire stale pending payments.

    Safety: this job only transitions rows that are *already* expired. It
    never deletes anything. Completed orders, payment records, wallet ledger
    entries, delivery records, support conversations and audit logs are
    explicitly out of scope and are not touched.
    """
    released = 0
    expired = 0
    async with async_session() as session:
        now = datetime.utcnow()

        # 1. Expired inventory reservations -> back to AVAILABLE.
        #    Conditional UPDATE: a reservation grabbed by a new checkout in the
        #    meantime has a future expiry and will not match.
        inv_result = await session.execute(
            update(Inventory)
            .where(
                and_(
                    Inventory.status == InventoryStatus.RESERVED,
                    Inventory.reservation_expires_at.isnot(None),
                    Inventory.reservation_expires_at < now,
                )
            )
            .values(
                status=InventoryStatus.AVAILABLE,
                reserved_at=None,
                reservation_expires_at=None,
                updated_at=now,
            )
            .returning(Inventory.id)
        )
        released = len(inv_result.scalars().all())
        if released:
            logger.info("Released %s expired reservation(s)", released)

        # 2. Stale pending payments (pending / waiting_user for >30 min).
        stale_payments = (
            select(Payment)
            .where(
                and_(
                    Payment.status.in_(
                        [PaymentStatus.PENDING, PaymentStatus.WAITING_USER]
                    ),
                    Payment.created_at < now - _payment_cutoff(),
                )
            )
            .order_by(Payment.created_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        payments = (await session.execute(stale_payments)).scalars().all()

        for payment in payments:
            await session.execute(
                update(Payment)
                .where(
                    and_(
                        Payment.id == payment.id,
                        Payment.status.in_(
                            [PaymentStatus.PENDING, PaymentStatus.WAITING_USER]
                        ),
                    )
                )
                .values(status=PaymentStatus.EXPIRED, updated_at=now)
            )
            expired += 1

            # Only cancel the order if it is still awaiting payment. If it was
            # paid in the meantime we must not cancel a paid order.
            if not payment.order_id:
                continue

            # Return the order's reserved inventory only if the order actually
            # transitioned, so we never release stock for a still-live order.
            cancelled = await session.execute(
                update(Order)
                .where(
                    and_(
                        Order.id == payment.order_id,
                        Order.status == OrderStatus.PENDING_PAYMENT,
                        Order.inventory_id.isnot(None),
                    )
                )
                .values(status=OrderStatus.CANCELLED, cancelled_at=now, updated_at=now)
                .returning(Order.inventory_id)
            )
            inventory_id = cancelled.scalar_one_or_none()
            if inventory_id is None:
                continue

            await session.execute(
                update(Inventory)
                .where(
                    and_(
                        Inventory.id == inventory_id,
                        Inventory.status == InventoryStatus.RESERVED,
                    )
                )
                .values(
                    status=InventoryStatus.AVAILABLE,
                    reserved_at=None,
                    reservation_expires_at=None,
                    updated_at=now,
                )
            )
            logger.info(
                "Cancelled order %s and released inventory %s",
                payment.order_id,
                inventory_id,
            )

        await session.commit()

    return released + expired


def _payment_cutoff() -> timedelta:
    return timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
