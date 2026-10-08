from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import PaymentStatus
from app.database.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Payment:
        payment = Payment(**data)
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: int) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def get_by_order(self, order_id: int, status: PaymentStatus | None = None) -> Payment | None:
        stmt = select(Payment).where(Payment.order_id == order_id)
        if status:
            stmt = stmt.where(Payment.status == status)
        stmt = stmt.order_by(Payment.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.external_payment_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_tracking_code(self, tracking_code: str) -> Payment | None:
        """Locate a payment from the gateway's return URL (ResNum)."""
        if not tracking_code:
            return None
        stmt = select(Payment).where(Payment.tracking_code == str(tracking_code))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update(self, payment_id: int) -> Payment | None:
        """Row-lock a payment for the duration of the surrounding transaction.

        This is what makes concurrent completion attempts (duplicate callback,
        reconciliation racing a user click, admin retry) serialize instead of
        both crediting the wallet.
        """
        stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, payment_id: int, new_status: PaymentStatus, extra: dict | None = None, commit: bool = True) -> Payment | None:
        payment = await self.get_by_id(payment_id)
        if not payment:
            return None
        payment.status = new_status
        if extra:
            for key, value in extra.items():
                setattr(payment, key, value)
        if new_status == PaymentStatus.PAID:
            payment.verified_at = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        if commit:
            await self.session.commit()
            await self.session.refresh(payment)
        return payment

    async def get_pending_verification(self) -> list[Payment]:
        stmt = select(Payment).where(Payment.status == PaymentStatus.PENDING_VERIFICATION)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_expired_pending(self) -> list[Payment]:
        # Payments pending or waiting user older than 30 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        stmt = select(Payment).where(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.WAITING_USER]),
            Payment.created_at < cutoff
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, status: PaymentStatus | None = None, limit: int = 100, offset: int = 0) -> list[Payment]:
        stmt = select(Payment)
        if status:
            stmt = stmt.where(Payment.status == status)
        stmt = stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
