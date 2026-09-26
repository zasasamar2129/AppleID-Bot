from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.enums import WalletTransactionType
from app.database.models.referral import Referral
from app.database.repositories.referral_repo import ReferralRepository
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.wallet_repo import WalletRepository


class ReferralService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.user_repo = UserRepository(session)
        self.wallet_repo = WalletRepository(session)

    async def generate_referral_link(self, user_id: int) -> str:
        bot_username = settings.telegram_bot_username
        if not bot_username:
            return f"https://t.me/your_bot?start=ref_{user_id}"
        return f"https://t.me/{bot_username}?start=ref_{user_id}"

    async def process_referral(self, referrer_id: int, referred_user_id: int) -> bool:
        if referrer_id == referred_user_id:
            return False
        # Check if already referred
        existing = await self.referral_repo.get_by_referred_user(referred_user_id)
        if existing:
            return False
        # Create referral
        await self.referral_repo.create(referrer_id, referred_user_id)
        # Give reward if configured
        reward = getattr(settings, "referral_reward", 0)
        if reward:
            wallet = await self.wallet_repo.get_or_create(referrer_id)
            wallet.balance += Decimal(reward)
            await self.wallet_repo.update_balance(wallet.id, wallet.balance)
            await self.wallet_repo.add_transaction(wallet.id, WalletTransactionType.REFERRAL, Decimal(reward), wallet.balance, reference_id=f"ref_{referred_user_id}", description="Referral reward")
            # Get the referral we just created
            new_ref = await self.referral_repo.get_by_referred_user(referred_user_id)
            if new_ref:
                await self.referral_repo.mark_reward_given(new_ref.id)
        return True

    async def get_referral_count(self, user_id: int) -> int:
        return await self.referral_repo.count_referrals(user_id)

    async def get_referrals(self, user_id: int) -> list[Referral]:
        return await self.referral_repo.get_referrals_by_referrer(user_id)
