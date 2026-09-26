from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)

logger = logging.getLogger(__name__)


async def safe_send_message(bot: Bot, chat_id: int, text: str, **kwargs) -> object | None:
    try:
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except TelegramRetryAfter as e:
        logger.warning(f"Rate limited, retry after {e.retry_after}")
    except (TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError) as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
    return None


async def safe_edit_message(bot: Bot, chat_id: int, message_id: int, text: str, **kwargs) -> object | None:
    try:
        return await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Edit message error: {e}")
    except (TelegramRetryAfter, TelegramForbiddenError, TelegramNetworkError) as e:
        logger.error(f"Edit message failed: {e}")
    return None
