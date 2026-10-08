from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.enums import PaymentMethod, PaymentStatus
from app.database.models.payment import Payment
from app.database.session import async_session
from app.services.payment_service import (
    PaymentService,
    claim_payment_for_processing,
    reconcilable_online_payments_query,
)
from app.workers.job_runner import scheduled_job

logger = logging.getLogger(__name__)

# Per-payment verification budget. One unresponsive call must not stall the run.
VERIFY_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS_PER_RUN = 25


async def _expire_stale_payments(session: AsyncSession) -> int:
    """Finalise online payments past their TTL that never reached the bank.

    Deliberately scoped to states where we never handed the user a token
    (or they abandoned it before the bank saw it): PENDING/WAITING_USER with
    no reference number. Anything carrying a RefNum stays reconcilable — the
    money may already have moved, and expiring it would lose the payment.
    """
    now = datetime.utcnow()
    stmt = (
        select(Payment)
        .where(
            Payment.method == PaymentMethod.ONLINE,
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.WAITING_USER]),
            Payment.reference_number.is_(None),
            Payment.expires_at.is_not(None),
            Payment.expires_at < now,
        )
        .limit(MAX_ATTEMPTS_PER_RUN)
    )
    result = await session.execute(stmt)
    stale = list(result.scalars().all())

    for payment in stale:
        payment.status = PaymentStatus.EXPIRED
        payment.failure_reason = payment.failure_reason or "expired"
        payment.updated_at = now
    if stale:
        await session.commit()
        logger.info("payment_reconciliation_expired count=%d", len(stale))
    return len(stale)


@scheduled_job(
    "payment_reconciliation", criticality="critical", slow_threshold=10.0, lock_ttl=180
)
async def payment_reconciliation_job() -> int:
    """Resolve online payments the gateway and the user have left open.

    Recovery model — survives restart, crash, and duplicate execution:

    * The durable source of truth is PostgreSQL. Nothing lives only in memory,
      so a process killed mid-run resumes from the same rows on the next tick.
    * Each row is claimed with a conditional UPDATE gated on status. A payment
      already finished by a parallel path no longer matches the claim, so the
      claim is a real ownership transfer rather than a timestamp bump.
    * Network I/O runs outside any transaction (see ``finalize_payment``), so
      a timeout leaves the row untouched and still reconcilable instead of
      half-written.
    * Completion is idempotent: re-running a finished payment returns
      ``already_completed`` and performs no second credit.
    * A miss is self-healing. The job runs on an interval with
      ``coalesce=True`` and ``misfire_grace_time=180``, so a backlog collapses
      into one execution and a late run still fires.
    """
    if not settings.payment_reconciliation_enabled:
        logger.debug("Payment reconciliation disabled; skipping")
        return 0

    resolved = 0
    async with async_session() as session:
        try:
            expired = await _expire_stale_payments(session)
            resolved += expired

            result = await session.execute(
                reconcilable_online_payments_query(MAX_ATTEMPTS_PER_RUN)
            )
            candidates = list(result.scalars().all())

            for payment in candidates:
                claimed = await claim_payment_for_processing(session, payment.id)
                if not claimed:
                    continue

                try:
                    async with asyncio.timeout(VERIFY_TIMEOUT_SECONDS):
                        outcome = await PaymentService(session).finalize_payment(payment.id)
                except TimeoutError:
                    # Provider never answered. Leave the row exactly as it was.
                    await session.rollback()
                    logger.warning(
                        "payment_reconciliation_timeout payment_id=%s budget=%.0fs",
                        payment.id,
                        VERIFY_TIMEOUT_SECONDS,
                    )
                    continue
                except Exception as exc:  # noqa: BLE001 - isolate one bad row
                    # Log the type only; provider payloads can carry details
                    # we do not want in the log stream.
                    await session.rollback()
                    logger.error(
                        "payment_reconciliation_error payment_id=%s error_type=%s",
                        payment.id,
                        type(exc).__name__,
                    )
                    continue

                if outcome.paid:
                    resolved += 1
                    logger.info(
                        "payment_reconciliation_success payment_id=%s already_completed=%s",
                        payment.id,
                        outcome.already_completed,
                    )
                elif outcome.amount_mismatch:
                    # Money question. Surface loudly rather than retry forever.
                    logger.error(
                        "payment_reconciliation_amount_mismatch payment_id=%s",
                        payment.id,
                    )
                elif outcome.reason not in {"", "verify_unavailable", "verify_error"}:
                    logger.info(
                        "payment_reconciliation_failed payment_id=%s reason=%s",
                        payment.id,
                        outcome.reason,
                    )
        finally:
            # Never leave a half-open transaction on the pooled session.
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001 - rollback must not mask the job error
                logger.exception("payment_reconciliation_rollback_failed")

    if resolved:
        logger.info("payment_reconciliation_done resolved=%d", resolved)
    return resolved
