from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.referral import Referral


class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, referrer_id: int, referred_user_id: int) -> Referral:
        ref = Referral(
            referrer_id=referrer_id,
            referred_user_id=referred_user_id,
            created_at=datetime.utcnow(),
        )
        self.session.add(ref)
        await self.session.commit()
        await self.session.refresh(ref)
        return ref

    async def get_by_referred_user(self, referred_user_id: int) -> Referral | None:
        stmt = select(Referral).where(Referral.referred_user_id == referred_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_reward_given(self, referral_id: int) -> None:
        ref = await self.session.get(Referral, referral_id)
        if ref:
            ref.reward_given = True
            ref.reward_given_at = datetime.utcnow()
            await self.session.commit()

    async def get_referrals_by_referrer(self, referrer_id: int) -> list[Referral]:
        stmt = select(Referral).where(Referral.referrer_id == referrer_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_referrals(self, referrer_id: int) -> int:
        stmt = select(Referral).where(Referral.referrer_id == referrer_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def count_all_referrals(self) -> int:
        stmt = select(func.count()).select_from(Referral)
        result = await self.session.execute(stmt)
        return result.scalar_one()
