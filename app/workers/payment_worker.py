from __future__ import annotations

import logging

from app.database.models.enums import PaymentStatus
from app.database.session import async_session
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


async def payment_reconciliation_job():
    async with async_session() as session:
        from app.database.repositories.payment_repo import PaymentRepository
        payment_repo = PaymentRepository(session)
        pending_payments = await payment_repo.get_pending_verification()
        for payment in pending_payments:
            # For online payments, we would call provider. For card-to-card, we just leave as pending.
            if payment.method == "online" and payment.status == PaymentStatus.PENDING:
                payment_service = PaymentService(session)
                try:
                    await payment_service.verify_online_payment(payment)
                except Exception as e:
                    logger.error(f"Payment reconciliation error for {payment.id}: {e}")
        await session.commit()
