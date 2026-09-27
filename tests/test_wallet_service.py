import pytest
from decimal import Decimal
from app.database.repositories.user_repo import UserRepository
from app.services.wallet_service import WalletService

@pytest.mark.asyncio
async def test_wallet_deposit_and_deduct(db_session):
    user_repo = UserRepository(db_session)
    user = await user_repo.create(telegram_id=123457, first_name="Test")
    wallet_service = WalletService(db_session)
    balance = await wallet_service.deposit(user.id, Decimal("50"))
    assert balance == Decimal("50")
    # Deduct
    success = await wallet_service.deduct(user.id, Decimal("20"))
    assert success is True
    balance = await wallet_service.get_balance(user.id)
    assert balance == Decimal("30")
    # Insufficient
    success = await wallet_service.deduct(user.id, Decimal("100"))
    assert success is False