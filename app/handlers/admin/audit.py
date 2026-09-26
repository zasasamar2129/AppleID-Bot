import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.callback_query(F.data == "admin:audit")
async def admin_audit_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    repo = AuditRepository(session)
    logs = await repo.get_recent(50)
    text = "Audit Logs:\n"
    for log in logs[:20]:
        text += f"- {log.action} on {log.target_type} ({log.created_at})\n"
    await callback.message.edit_text(text)
    await callback.answer()
