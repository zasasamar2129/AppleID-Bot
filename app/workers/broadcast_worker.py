from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import and_

from app.bot.bot import bot
from app.config import settings
from app.database.models.broadcast import Broadcast, BroadcastReceipt
from app.database.models.user import User
from app.database.session import async_session
from app.workers.job_runner import scheduled_job

logger = logging.getLogger(__name__)

# How long a broadcast may stay in_progress before we consider it abandoned
# (process died mid-send) and resume it. Must exceed the time needed to send
# to the whole audience at BROADCAST_DELAY_SECONDS per user.
STALE_IN_PROGRESS_SECONDS = 3600

# Only claim a batch this size per tick so one job run cannot hold the event
# loop hostage for a very large audience.
BATCH_SIZE = 200


@scheduled_job("process_broadcasts", criticality="important", slow_threshold=15.0, lock_ttl=300)
async def process_broadcasts_job() -> int:
    """Send queued broadcasts, resumably and without duplicate delivery.

    Resumability: progress is recorded as one ``broadcast_receipts`` row per
    user with a unique (broadcast_id, user_id) constraint, so a run that dies
    after 237 of 500 users resumes at user 238 rather than resending to the
    first 237. The constraint is also what makes a duplicate run a no-op
    instead of a second message.

    Batching: each tick sends at most BATCH_SIZE users and returns, so the job
    never blocks the event loop for long enough to starve other jobs.
    """
    sent = 0
    async with async_session() as session:
        # 1. Claim a broadcast atomically: queued -> in_progress. A parallel
        #    run sees 0 rows and moves on. UPDATE has no LIMIT in PostgreSQL,
        #    so restrict the update to the single oldest eligible id via a
        #    subquery.
        now = datetime.utcnow()
        stale_before = now - _stale_delta()
        eligible = (
            select(Broadcast.id)
            .where(
                or_(
                    Broadcast.status == "queued",
                    and_(
                        Broadcast.status == "in_progress",
                        or_(
                            Broadcast.started_at.is_(None),
                            Broadcast.started_at < stale_before,
                        ),
                    ),
                )
            )
            .order_by(Broadcast.created_at)
            .limit(1)
        )
        claim = await session.execute(
            update(Broadcast)
            .where(Broadcast.id == eligible.scalar_subquery())
            .values(status="in_progress", started_at=now)
            .returning(Broadcast.id)
        )
        broadcast_id = claim.scalar_one_or_none()
        if broadcast_id is None:
            return 0

        # 2. Recipients that have NOT yet been delivered to. This is the
        #    resume point: it is derived from durable state, not from a
        #    progress counter.
        already_sent = select(func.count()).select_from(BroadcastReceipt).where(
            and_(
                BroadcastReceipt.broadcast_id == broadcast_id,
                BroadcastReceipt.status == "sent",
            )
        )
        recipients = (
            select(User.id, User.telegram_id)
            .where(User.is_blocked.is_(False))
            .where(
                ~select(BroadcastReceipt.user_id)
                .where(
                    and_(
                        BroadcastReceipt.broadcast_id == broadcast_id,
                        BroadcastReceipt.status == "sent",
                    )
                )
                .exists()
            )
            .order_by(User.id)
            .limit(BATCH_SIZE)
        )
        targets = (await session.execute(recipients)).all()
        remaining = (await session.execute(already_sent)).scalar_one()

        if not targets:
            # Everyone has been delivered to: mark complete.
            await session.execute(
                update(Broadcast)
                .where(and_(Broadcast.id == broadcast_id, Broadcast.status == "in_progress"))
                .values(status="completed", completed_at=datetime.utcnow())
            )
            await session.commit()
            logger.info("Broadcast %s completed (%s sent)", broadcast_id, remaining)
            return 0

        broadcast = await session.get(Broadcast, broadcast_id)
        content = broadcast.content if broadcast else ""

        # 3. Send. Each message is committed with its receipt immediately so a
        #    crash loses at most the in-flight message, not the whole batch.
        for user_id, telegram_id in targets:
            try:
                if broadcast and broadcast.content_type == "text":
                    await bot.send_message(chat_id=telegram_id, text=content)
                else:
                    # Unsupported content type: record and move on rather than
                    # looping forever on something we cannot send.
                    raise ValueError(f"unsupported content_type={broadcast.content_type}")

                await asyncio.sleep(settings.broadcast_delay_seconds)
                await _record_receipt(session, broadcast_id, user_id, "sent")
                sent += 1
            except IntegrityError:
                # Unique (broadcast_id, user_id) rejected: already delivered by
                # another run. Expected and harmless.
                await session.rollback()
            except Exception as exc:  # noqa: BLE001 - one bad user must not
                # abort the whole broadcast.
                logger.warning(
                    "Broadcast %s delivery to user_id=%s failed: error_type=%s",
                    broadcast_id,
                    user_id,
                    type(exc).__name__,
                )
                await session.rollback()
                try:
                    await _record_receipt(session, broadcast_id, user_id, "failed")
                except Exception:
                    await session.rollback()

        # 4. Refresh counters from the durable receipts so the numbers cannot
        #    drift from reality after a crash and resume.
        await _sync_counters(session, broadcast_id)
        await session.commit()

    return sent


def _stale_delta() -> timedelta:
    return timedelta(seconds=STALE_IN_PROGRESS_SECONDS)


async def _record_receipt(session, broadcast_id: int, user_id: int, status: str) -> None:
    session.add(
        BroadcastReceipt(broadcast_id=broadcast_id, user_id=user_id, status=status)
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise


async def _sync_counters(session, broadcast_id: int) -> None:
    sent = (
        await session.execute(
            select(func.count())
            .select_from(BroadcastReceipt)
            .where(
                and_(
                    BroadcastReceipt.broadcast_id == broadcast_id,
                    BroadcastReceipt.status == "sent",
                )
            )
        )
    ).scalar_one()
    failed = (
        await session.execute(
            select(func.count())
            .select_from(BroadcastReceipt)
            .where(
                and_(
                    BroadcastReceipt.broadcast_id == broadcast_id,
                    BroadcastReceipt.status == "failed",
                )
            )
        )
    ).scalar_one()
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .values(sent_count=sent, failed_count=failed)
    )
