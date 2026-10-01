from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import settings
from app.localization import get_text

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Silently acknowledge pagination indicator buttons and similar inert controls."""
    await callback.answer()


@router.errors()
async def error_handler(event):
    """Last-resort notification when an update fails.

    Deliberately avoids the database. This handler runs *during* incidents, and
    opening a new session here meant a DB outage turned one failure into two —
    leaving the user with no reply at all. The language comes from the update
    context instead.
    """
    logger.error(
        "Update %s caused error: %s",
        getattr(event.update, "update_id", "?"),
        event.exception,
        exc_info=event.exception,
    )

    # The resolved language lives on the handler kwargs, which ErrorEvent does
    # not carry, so fall back to the configured default rather than risking a
    # database call during an incident.
    lang = settings.default_language

    try:
        if event.update.message:
            await event.update.message.answer(get_text("errors.general", lang))
        elif event.update.callback_query:
            await event.update.callback_query.answer(
                get_text("errors.general", lang), show_alert=True
            )
    except Exception as e:
        # Log loudly: this is the end of the line, so a failure here means the
        # user genuinely received nothing.
        logger.error(
            "Failed to notify user of error (user saw nothing): %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
