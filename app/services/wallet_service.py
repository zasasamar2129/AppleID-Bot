from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import WalletTransactionType
from app.database.models.wallet import WalletTransaction
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.wallet_repo import WalletRepository


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.wallet_repo = WalletRepository(session)
        self.order_repo = OrderRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def get_balance(self, user_id: int) -> Decimal:
        wallet = await self.wallet_repo.get_or_create(user_id)
        return wallet.balance

    async def deposit(self, user_id: int, amount: Decimal, txn_type: WalletTransactionType = WalletTransactionType.DEPOSIT, reference_id: str | None = None, description: str | None = None) -> Decimal:
        wallet = await self.wallet_repo.get_or_create(user_id)
        if reference_id:
            existing = await self.wallet_repo.get_transaction_by_reference(reference_id)
            if existing:
                return wallet.balance
        wallet.balance += amount
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)
        await self.wallet_repo.add_transaction(wallet.id, txn_type, amount, wallet.balance, reference_id=reference_id, description=description)
        return wallet.balance

    async def deduct(self, user_id: int, amount: Decimal, txn_type: WalletTransactionType = WalletTransactionType.PURCHASE, reference_id: str | None = None, description: str | None = None) -> bool:
        wallet = await self.wallet_repo.get_or_create(user_id)
        if wallet.balance < amount:
            return False
        wallet.balance -= amount
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)
        await self.wallet_repo.add_transaction(wallet.id, txn_type, -amount, wallet.balance, reference_id=reference_id, description=description)
        return True

    async def admin_adjust(self, user_id: int, amount: Decimal, reason: str | None = None, admin_id: int | None = None) -> Decimal:
        wallet = await self.wallet_repo.get_or_create(user_id)
        wallet.balance += amount
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)
        await self.wallet_repo.add_transaction(
            wallet.id,
            WalletTransactionType.ADMIN_ADJUSTMENT,
            amount,
            wallet.balance,
            reference_id=f"admin_{admin_id}" if admin_id else None,
            description=reason,
        )
        return wallet.balance

    async def get_transaction_history(self, user_id: int, limit: int = 20, offset: int = 0) -> list[WalletTransaction]:
        wallet = await self.wallet_repo.get_or_create(user_id)
        return await self.wallet_repo.get_transactions(wallet.id, limit, offset)
