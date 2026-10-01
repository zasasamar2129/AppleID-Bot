from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.bot import bot
from app.bot.keyboards.channel import membership_gate_keyboard, membership_gate_text
from app.config import settings
from app.services.channel_membership_service import ChannelMembershipService

logger = logging.getLogger(__name__)


class ChannelMembershipMiddleware(BaseMiddleware):
    """Block all customer updates unless the user is a verified channel member.

    Runs on every update (start, callbacks, FSM steps, old keyboards). Admins
    bypass via the existing RBAC (env ADMIN_IDS + admin_users table). Blocks by
    early-returning before the handler, mirroring MaintenanceMiddleware.

    Invariant: a non-member always receives *some* reply. If the membership check
    or the gate render fails (Redis down, Telegram API error, network hiccup), we
    fall back to sending the gate directly rather than propagating — propagating
    produced total silence, which is indistinguishable to the user from being
    blocked and is invisible to the operator beyond a single log line.
    """

    def __init__(self) -> None:
        self.service = ChannelMembershipService(bot)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await self._handle(handler, event, data)
        except Exception:
            # Fail CLOSED: an unverifiable user is treated as a non-member.
            # Failing open would grant access we could not verify.
            logger.exception(
                "Membership gate failed for user_id=%s; failing closed",
                getattr(data.get("event_from_user"), "id", None),
            )
            await self._send_gate_directly(event, data)
            return None

    async def _handle(
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

        logger.info("Blocking non-member user_id=%s", user_id)
        # Not a member: block and show the membership gate.
        lang = data.get("lang", settings.default_language)

        # Clear any in-progress FSM so users are never trapped mid-flow.
        fsm_context = data.get("state")
        if fsm_context is not None:
            try:
                await fsm_context.clear()
            except Exception:
                logger.debug("Could not clear FSM state for non-member", exc_info=True)

        await self._render_gate(event, lang)

        # Blocked: do not call the handler.
        return None

    async def _render_gate(self, event: TelegramObject, lang: str) -> None:
        """Show the gate via MessageCleanupService (preferred path)."""
        from app.utils.message_manager import MessageCleanupService

        # Extract actual content if wrapped in an Update object
        from aiogram.types import Update
        if isinstance(event, Update):
            event = event.message or (event.callback_query.message if event.callback_query else None)

        if not event:
            logger.warning("Could not render gate: no message/callback found in Update.")
            return

        logger.info("Rendering gate for event type: %s", type(event))

        if isinstance(event, Message):
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
        else:
            logger.warning("Could not render gate: event is not Message or CallbackQuery with message.")


    async def _send_gate_directly(self, event: TelegramObject, data: dict[str, Any]) -> None:
        """Last-resort gate render that bypasses Redis/DB entirely.

        ``membership_gate_text`` / ``membership_gate_keyboard`` are pure functions
        over settings and static localization, so this still works when the very
        dependency that broke (Redis, the DB, the cleanup service) is unavailable.

        Uses ``bot.send_message`` rather than ``event.answer`` because a
        TelegramMethod built off the event is not bound to a bot instance and
        raises ``RuntimeError`` when awaited directly — the same reason the rest
        of the project sends via the bot.
        """
        lang = data.get("lang", settings.default_language)
        text = membership_gate_text(lang)
        markup = membership_gate_keyboard(lang)

        from aiogram.types import Update
        if isinstance(event, Update):
            event = event.message or (event.callback_query.message if event.callback_query else None)

        chat_id: int | None = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id

        if chat_id is None:
            return

        try:
            await bot.send_message(
                chat_id=chat_id, text=text, reply_markup=markup
            )
        except Exception:
            # Nothing further we can do; the failure is already logged above.
            logger.exception("Emergency membership gate could not be delivered")
            return

        # Always answer the callback so the button stops spinning, even if the
        # gate itself could not be rendered.
        if isinstance(event, CallbackQuery):
            try:
                await event.answer()
            except Exception:
                logger.debug("Could not answer callback in gate fallback", exc_info=True)
