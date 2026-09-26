import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.support_repo import SupportRepository

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.callback_query(F.data == "admin:support")
async def admin_support_menu(callback: CallbackQuery, lang="fa"):
    await callback.message.answer("Support tickets: /tickets")
    await callback.answer()

@router.message(F.text == "/tickets")
async def admin_tickets(message: Message, session: AsyncSession, lang="fa"):
    repo = SupportRepository(session)
    tickets = await repo.get_all_tickets()
    if not tickets:
        await message.answer("No tickets.")
        return
    text = "Tickets:\n"
    for t in tickets[:10]:
        text += f"#{t.id} - {t.subject} - {t.status.value}\n"
    await message.answer(text)
