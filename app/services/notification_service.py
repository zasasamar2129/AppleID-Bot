from __future__ import annotations

from typing import Any

from aiogram import Bot

from app.config import settings
from app.localization import get_text
from app.utils.formatting import format_price


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def notify_user(self, user_id: int, key: str, lang: str = "fa", **kwargs: Any) -> None:
        text = get_text(key, lang, **kwargs)
        try:
            await self.bot.send_message(chat_id=user_id, text=text)
        except Exception:
            pass

    async def notify_admins_new_payment(self, payment):
        amount_str = format_price(payment.amount, settings.default_language)
        # Wallet top-ups have no order; display a clear label in that case.
        order_ref = f"Order #{payment.order_id}" if payment.order_id else "Wallet top-up"
        for admin_id in settings.admin_ids_list:
            try:
                await self.bot.send_message(
                    admin_id,
                    f"💳 New Payment Verification\n\n{order_ref}\nAmount: {amount_str}\nPlease review."
                )
            except Exception:
                pass
