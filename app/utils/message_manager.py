from __future__ import annotations

import logging
from enum import Enum

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from app.bot.bot import bot, redis_client

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    UI = "ui"
    TEMPORARY = "temporary"
    PROMPT = "prompt"
    DELIVERY = "delivery"
    PAYMENT = "payment"
    RECEIPT = "receipt"
    ORDER_CONFIRMATION = "order_confirmation"
    SUPPORT = "support"
    SYSTEM = "system"


# Message types that must NEVER be removed by automatic cleanup.
PROTECTED_TYPES = {
    MessageType.DELIVERY,
    MessageType.PAYMENT,
    MessageType.RECEIPT,
    MessageType.ORDER_CONFIRMATION,
    MessageType.SUPPORT,
    MessageType.SYSTEM,
}


class MessageCleanupService:
    """Centralized message lifecycle manager.

    Responsibilities:
    - Edit the current UI screen in place when possible (no orphaned messages).
    - Track message ownership + type in Redis.
    - Delete obsolete temporary/UI messages, never business-critical ones.
    - Fail gracefully when Telegram or Redis is unavailable.
    """

    # TTL for tracked message state (seconds)
    UI_MESSAGE_TTL = 1800
    TEMPORARY_MESSAGE_TTL = 300

    @staticmethod
    async def _get_last_ui_id(chat_id: int) -> int | None:
        try:
            value = await redis_client.get(f"ui:last:{chat_id}")
            return int(value) if value else None
        except Exception:
            return None

    @staticmethod
    async def _set_last_ui_id(chat_id: int, message_id: int) -> None:
        try:
            await redis_client.set(f"ui:last:{chat_id}", message_id, ex=MessageCleanupService.UI_MESSAGE_TTL)
        except Exception:
            pass

    @staticmethod
    async def _register_message(chat_id: int, message_id: int, msg_type: MessageType) -> None:
        try:
            key = f"msg:{chat_id}:{message_id}"
            await redis_client.set(key, msg_type.value, ex=MessageCleanupService.UI_MESSAGE_TTL)
        except Exception:
            pass

    @staticmethod
    async def _get_message_type(chat_id: int, message_id: int) -> MessageType | None:
        try:
            key = f"msg:{chat_id}:{message_id}"
            val = await redis_client.get(key)
            return MessageType(val) if val else None
        except Exception:
            return None

    @staticmethod
    async def _forget_message(chat_id: int, message_id: int) -> None:
        try:
            await redis_client.delete(f"msg:{chat_id}:{message_id}")
        except Exception:
            pass

    @staticmethod
    async def _forget_last_ui(chat_id: int) -> None:
        try:
            await redis_client.delete(f"ui:last:{chat_id}")
        except Exception:
            pass

    @staticmethod
    async def _delete_message(chat_id: int, message_id: int) -> None:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest:
            # Message already gone or too old — no action needed.
            return
        except TelegramForbiddenError:
            # Bot cannot delete in this chat — no action needed.
            return
        except Exception as e:
            logger.warning(f"Could not delete message {message_id} in chat {chat_id}: {e}")

    @classmethod
    async def show_screen(
        cls,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str = "HTML",
        protected: bool = False,
        force_new: bool = False,
    ) -> int:
        """Render a UI screen.

        Preferred: edit the currently tracked UI message in place.
        Fallback: delete obsolete UI + send a fresh message and track it.
        If `protected` is True, the message is registered as a protected type
        so it is never removed by automatic cleanup.
        If `force_new` is True, always delete old UI and send a fresh message
        (used for back navigation so the old menu is deleted).
        """
        if not force_new:
            last_ui_id = await cls._get_last_ui_id(chat_id)
            if last_ui_id:
                msg_type = await cls._get_message_type(chat_id, last_ui_id)
                if msg_type == MessageType.UI:
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=last_ui_id,
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode,
                        )
                        return last_ui_id
                    except TelegramBadRequest:
                        # Not editable (e.g. too old, media message). Fall through to send new.
                        pass
                    except TelegramForbiddenError:
                        # Bot cannot edit here. Fall through to send new.
                        pass
                    except Exception as e:
                        logger.warning(f"Edit of screen in chat {chat_id} failed: {e}")

        await cls._delete_old_ui_messages(chat_id)

        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        msg_type = MessageType.SYSTEM if protected else MessageType.UI
        await cls._set_last_ui_id(chat_id, sent.message_id)
        await cls._register_message(chat_id, sent.message_id, msg_type)
        return sent.message_id

    @classmethod
    async def send_temporary(
        cls,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str = "HTML",
    ) -> int:
        """Send a temporary prompt/message that should be cleaned automatically later."""
        sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        await cls._register_message(chat_id, sent.message_id, MessageType.TEMPORARY)
        return sent.message_id

    @classmethod
    async def protect_message(cls, chat_id: int, message_id: int, msg_type: MessageType = MessageType.DELIVERY) -> None:
        """Mark a message as protected so it's not deleted by normal cleanup."""
        await cls._register_message(chat_id, message_id, msg_type)

    @classmethod
    async def delete_message(cls, chat_id: int, message_id: int) -> None:
        """Delete a specific tracked message (unless it is protected)."""
        msg_type = await cls._get_message_type(chat_id, message_id)
        if msg_type and msg_type in PROTECTED_TYPES:
            logger.warning(f"Attempt to delete protected message {message_id} of type {msg_type}. Ignored.")
            return
        await cls._delete_message(chat_id, message_id)
        await cls._forget_message(chat_id, message_id)

    @classmethod
    async def close(cls, chat_id: int) -> None:
        """Close current UI: delete the current UI message plus temporary/prompt
        messages left over from FSM flows, leaving protected business messages."""
        last_ui_id = await cls._get_last_ui_id(chat_id)
        if last_ui_id:
            await cls.delete_message(chat_id, last_ui_id)
            await cls._forget_last_ui(chat_id)
        # Also remove temporary/prompt messages (e.g. FSM prompts) that the
        # section may have spawned, so nothing is left behind on close.
        try:
            keys = await redis_client.keys(f"msg:{chat_id}:*")
            for key in keys:
                try:
                    message_id = int(key.decode().split(":")[-1])
                except (ValueError, AttributeError):
                    continue
                msg_type = await cls._get_message_type(chat_id, message_id)
                if msg_type in (MessageType.TEMPORARY, MessageType.PROMPT):
                    await cls._delete_message(chat_id, message_id)
                    await cls._forget_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Error during temporary cleanup in chat {chat_id}: {e}")

    @classmethod
    async def _delete_old_ui_messages(cls, chat_id: int) -> None:
        """Delete all tracked UI messages for this chat (never protected ones)."""
        try:
            keys = await redis_client.keys(f"msg:{chat_id}:*")
            for key in keys:
                try:
                    message_id = int(key.decode().split(":")[-1])
                except (ValueError, AttributeError):
                    continue
                msg_type = await cls._get_message_type(chat_id, message_id)
                if msg_type == MessageType.UI:
                    await cls._delete_message(chat_id, message_id)
                    await cls._forget_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Error during old UI cleanup in chat {chat_id}: {e}")

    @classmethod
    async def cleanup_user_ui(cls, chat_id: int) -> None:
        """Clean up all temporary and UI messages for a user, leaving protected ones."""
        await cls._delete_old_ui_messages(chat_id)
        await cls._forget_last_ui(chat_id)
        # Delete temporary/prompt messages — business-critical ones are protected.
        try:
            keys = await redis_client.keys(f"msg:{chat_id}:*")
            for key in keys:
                try:
                    message_id = int(key.decode().split(":")[-1])
                except (ValueError, AttributeError):
                    continue
                msg_type = await cls._get_message_type(chat_id, message_id)
                if msg_type in (MessageType.TEMPORARY, MessageType.PROMPT):
                    await cls._delete_message(chat_id, message_id)
                    await cls._forget_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Error during temporary cleanup in chat {chat_id}: {e}")
