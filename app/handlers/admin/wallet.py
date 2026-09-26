import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.callback_query(F.data == "admin:wallet")
async def admin_wallet_menu(callback: CallbackQuery, lang="fa"):
    await callback.message.answer("Use /wallet_adjust <user_id> <amount> to adjust")
    await callback.answer()

@router.message(F.text.startswith("/wallet_adjust"))
async def admin_wallet_adjust(message: Message, session: AsyncSession, lang="fa"):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /wallet_adjust <user_id> <amount>")
        return
    try:
        user_id = int(parts[1])
        amount = float(parts[2])
    except:
        await message.answer("Invalid parameters")
        return
    wallet_service = WalletService(session)
    await wallet_service.admin_adjust(user_id, amount, reason="Admin command")
    await message.answer("Wallet adjusted.")
