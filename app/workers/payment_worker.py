from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.sql import and_

from app.database.models.enums import PaymentMethod, PaymentStatus
from app.database.models.payment import Payment
from app.database.session import async_session
from app.services.payment_service import PaymentService
from app.workers.job_runner import scheduled_job

logger = logging.getLogger(__name__)

# Per-payment verification attempt with a hard timeout so one unresponsive
# provider call cannot stall the whole job.
VERIFY_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS_PER_RUN = 25


@scheduled_job(
    "payment_reconciliation", criticality="critical", slow_threshold=10.0, lock_ttl=120
)
async def payment_reconciliation_job() -> int:
    """Re-check pending online payments against the provider.

    Idempotency: each payment is claimed with a conditional UPDATE that also
    bumps ``updated_at``; a payment already verified by a parallel run no
    longer matches PENDING_VERIFICATION and is skipped. A provider timeout
    rolls that one payment back and leaves it for the next run rather than
    failing the whole batch.
    """
    from app.config import settings

    if not settings.payment_reconciliation_enabled:
        logger.debug("Payment reconciliation disabled; skipping")
        return 0

    reconciled = 0
    async with async_session() as session:
        # Only ONLINE payments need provider verification. Card-to-card
        # payments are settled by an admin and must not be touched here.
        stmt = (
            select(Payment)
            .where(
                and_(
                    Payment.status == PaymentStatus.PENDING_VERIFICATION,
                    Payment.method == PaymentMethod.ONLINE,
                )
            )
            .order_by(Payment.created_at)
            .limit(MAX_ATTEMPTS_PER_RUN)
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        for payment in candidates:
            # Claim: only act if still PENDING_VERIFICATION. updated_at is
            # bumped as a heartbeat so a slow provider call is not re-claimed
            # by the next run while we are still waiting on it.
            claim = await session.execute(
                update(Payment)
                .where(
                    and_(
                        Payment.id == payment.id,
                        Payment.status == PaymentStatus.PENDING_VERIFICATION,
                    )
                )
                .values(updated_at=datetime.utcnow())
            )
            if claim.rowcount == 0:
                continue

            try:
                async with asyncio.timeout(VERIFY_TIMEOUT_SECONDS):
                    payment_service = PaymentService(session)
                    paid = await payment_service.verify_online_payment(payment)
                if paid:
                    reconciled += 1
                    logger.info("Reconciled online payment %s", payment.id)
            except TimeoutError:
                logger.warning(
                    "Payment %s verification timed out after %.0fs; will retry",
                    payment.id,
                    VERIFY_TIMEOUT_SECONDS,
                )
                # Leave it PENDING_VERIFICATION for the next run.
                await session.rollback()
            except Exception as exc:  # noqa: BLE001 - one bad payment must not
                # fail the batch. Log the type only; provider errors can carry
                # credentials in their message.
                logger.error(
                    "Payment %s reconciliation failed: error_type=%s",
                    payment.id,
                    type(exc).__name__,
                )
                await session.rollback()

        await session.commit()

    return reconciled
