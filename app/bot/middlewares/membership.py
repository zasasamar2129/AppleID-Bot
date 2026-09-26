from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.bot import bot
from app.bot.keyboards.channel import membership_gate_keyboard, membership_gate_text
from app.config import settings
from app.localization import get_text
from app.services.channel_membership_service import ChannelMembershipService
from app.utils.message_manager import MessageCleanupService


class ChannelMembershipMiddleware(BaseMiddleware):
    """Block all customer updates unless the user is a verified channel member.

    Runs on every update (start, callbacks, FSM steps, old keyboards). Admins
    bypass via the existing RBAC (env ADMIN_IDS + admin_users table). Blocks by
    early-returning before the handler, mirroring MaintenanceMiddleware.
    """

    def __init__(self) -> None:
        self.service = ChannelMembershipService(bot)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user = data.get("event_from_user")

        # Non-user events (chat member updates, etc.) — nothing to gate.
        if aiogram_user is None:
            return await handler(event, data)

        user_id = aiogram_user.id

        # Admins bypass the customer channel requirement.
        if await self.service.is_admin(user_id):
            return await handler(event, data)

        # The check-membership button must always reach its handler, even for
        # non-members, so they can verify after joining the channel.
        if isinstance(event, CallbackQuery) and event.data == "channel:check":
            return await handler(event, data)

        if await self.service.is_member(user_id):
            return await handler(event, data)

        # Not a member: block and show the membership gate.
        lang = data.get("lang", settings.default_language)

        # Clear any in-progress FSM so users are never trapped mid-flow.
        fsm_context = data.get("state")
        if fsm_context is not None:
            try:
                await fsm_context.clear()
            except Exception:
                pass

        if isinstance(event, Message):
            # `/start` deletes its own message; still render the gate via
            # show_screen (edits if the last UI exists, else sends fresh).
            await MessageCleanupService.show_screen(
                chat_id=event.chat.id,
                text=membership_gate_text(lang),
                reply_markup=membership_gate_keyboard(lang),
                force_new=True,
            )
        elif isinstance(event, CallbackQuery) and event.message:
            await MessageCleanupService.show_screen(
                chat_id=event.message.chat.id,
                text=membership_gate_text(lang),
                reply_markup=membership_gate_keyboard(lang),
                force_new=True,
            )
            try:
                await event.answer()
            except Exception:
                pass

        # Blocked: do not call the handler.
        return