from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=settings.timezone)


def setup_scheduler():
    from app.workers.broadcast_worker import process_broadcasts_job
    from app.workers.cleanup_worker import cleanup_expired_job
    from app.workers.order_worker import process_paid_orders_job
    from app.workers.payment_worker import payment_reconciliation_job

    scheduler.add_job(payment_reconciliation_job, "interval", seconds=settings.payment_reconciliation_interval_seconds, id="payment_reconciliation")
    scheduler.add_job(cleanup_expired_job, "interval", seconds=60, id="cleanup_expired")
    scheduler.add_job(process_paid_orders_job, "interval", seconds=30, id="process_orders")
    scheduler.add_job(process_broadcasts_job, "interval", seconds=10, id="process_broadcasts")
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped")
