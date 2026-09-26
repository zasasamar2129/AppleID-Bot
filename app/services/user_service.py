from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.database.repositories.referral_repo import ReferralRepository
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.wallet_repo import WalletRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.user_repo = UserRepository(session)
        self.wallet_repo = WalletRepository(session)
        self.referral_repo = ReferralRepository(session)

    async def register_user(self, telegram_id: int, first_name: str, username: str | None = None, last_name: str | None = None, language: str = "fa", referrer_id: int | None = None) -> User:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if user:
            # update last active
            await self.user_repo.update_last_active(telegram_id)
            return user
        user = await self.user_repo.create(telegram_id=telegram_id, first_name=first_name, username=username, last_name=last_name, language=language)
        # create wallet
        await self.wallet_repo.get_or_create(user.id)
        # process referral if provided
        if referrer_id and referrer_id != user.id:
            # check if already referred
            existing = await self.referral_repo.get_by_referred_user(user.id)
            if not existing:
                # check referrer exists
                referrer = await self.user_repo.get_by_id(referrer_id)
                if referrer:
                    await self.user_repo.update_referrer(user.id, referrer_id)
                    await self.referral_repo.create(referrer_id=referrer_id, referred_user_id=user.id)
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.user_repo.get_by_telegram_id(telegram_id)

    async def update_language(self, telegram_id: int, language: str) -> None:
        await self.user_repo.update_language(telegram_id, language)

    async def set_blocked(self, user_id: int, blocked: bool) -> None:
        await self.user_repo.set_blocked(user_id, blocked)

    async def set_vip(self, user_id: int, vip: bool) -> None:
        await self.user_repo.set_vip(user_id, vip)

    async def get_user_profile(self, user_id: int) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    async def count_users(self) -> int:
        return await self.user_repo.count()

    async def search_users(self, query: str) -> list[User]:
        return await self.user_repo.search(query)
