from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.localization import get_text

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Silently acknowledge pagination indicator buttons and similar inert controls."""
    await callback.answer()


@router.errors()
async def error_handler(event):
    logger.error(f"Update {event.update.update_id} caused error: {event.exception}", exc_info=True)
    # Try to infer the user's language to show a friendly, localized error.
    lang = "fa"
    user = getattr(event.update, "message", None)
    if user and getattr(user, "from_user", None):
        from app.config import settings
        from app.database.repositories.user_repo import UserRepository
        from app.database.session import async_session
        try:
            async with async_session() as session:
                db_user = await UserRepository(session).get_by_telegram_id(user.from_user.id)
                if db_user:
                    lang = db_user.language or settings.default_language
        except Exception:
            pass
    try:
        if event.update.message:
            await event.update.message.answer(get_text("errors.general", lang))
        elif event.update.callback_query:
            await event.update.callback_query.answer(get_text("errors.general", lang), show_alert=True)
    except Exception as e:
        logger.error(f"Failed to notify user of error: {e}")
