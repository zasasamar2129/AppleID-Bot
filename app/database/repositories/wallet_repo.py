from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import WalletTransactionType
from app.database.models.wallet import Wallet, WalletTransaction


class WalletRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> Wallet:
        wallet = await self.get_by_user(user_id)
        if not wallet:
            wallet = Wallet(user_id=user_id, balance=Decimal("0"), currency="IRR")
            self.session.add(wallet)
            await self.session.commit()
            await self.session.refresh(wallet)
        return wallet

    async def get_by_user(self, user_id: int) -> Wallet | None:
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_balance(self, wallet_id: int, new_balance: Decimal) -> None:
        wallet = await self.session.get(Wallet, wallet_id)
        if wallet:
            wallet.balance = new_balance
            await self.session.commit()

    async def add_transaction(self, wallet_id: int, txn_type: WalletTransactionType, amount: Decimal, balance_after: Decimal, reference_id: str | None = None, description: str | None = None) -> WalletTransaction:
        txn = WalletTransaction(
            wallet_id=wallet_id,
            type=txn_type,
            amount=amount,
            balance_after=balance_after,
            reference_id=reference_id,
            description=description,
        )
        self.session.add(txn)
        await self.session.commit()
        await self.session.refresh(txn)
        return txn

    async def get_transactions(self, wallet_id: int, limit: int = 20, offset: int = 0) -> list[WalletTransaction]:
        stmt = select(WalletTransaction).where(WalletTransaction.wallet_id == wallet_id).order_by(WalletTransaction.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
