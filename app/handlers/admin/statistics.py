import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.services.statistics_service import StatisticsService

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.callback_query(F.data == "admin:statistics")
async def admin_statistics_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    stats_service = StatisticsService(session)
    stats = await stats_service.get_dashboard_stats("all")
    text = f"Statistics:\nTotal Users: {stats['total_users']}\nTotal Orders: {stats['total_orders']}\nRevenue: {stats['revenue']}"
    await callback.message.edit_text(text)
    await callback.answer()
