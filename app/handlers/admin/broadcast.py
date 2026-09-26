import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.services.broadcast_service import BroadcastService
from app.states.admin.broadcast import AdminBroadcastStates

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.answer("Send broadcast text:")
    await state.set_state(AdminBroadcastStates.CONTENT)
    await callback.answer()

@router.message(AdminBroadcastStates.CONTENT)
async def admin_broadcast_content(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    content = message.text
    # For now, broadcast to all users (simplified)
    broadcast_service = BroadcastService(session)
    b = await broadcast_service.create_broadcast(message.from_user.id, "text", content, audience_filter={"all": True})
    await broadcast_service.queue_broadcast(b.id, target_count=0)  # count will be computed by worker
    await message.answer("Broadcast queued.")
    await state.clear()
