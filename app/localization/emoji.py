from __future__ import annotations

from app.config import settings


class Emoji:
    CART = settings.emoji_cart or "🛒"
    WALLET = settings.emoji_wallet or "💰"
    SUCCESS = settings.emoji_success or "✅"
    ERROR = settings.emoji_error or "❌"
    LOADING = settings.emoji_loading or "⏳"
    APPLE = settings.emoji_apple or "🍎"
    GIFT = settings.emoji_gift or "🎁"
    SUPPORT = settings.emoji_support or "🎧"
    BACK = "⬅️"
    NEXT = "➡️"
    INFO = "ℹ️"
    WARNING = "⚠️"
    LOCK = "🔒"
    UNLOCK = "🔓"
    STAR = "⭐"
    FIRE = "🔥"
    NEW = "🆕"
    PREMIUM = "💎"
    INSTANT = "⚡"
    CHECK = "✅"
    CROSS = "❌"
    CLOCK = "🕐"
    MONEY = "💵"
    CARD = "💳"
    RECEIPT = "🧾"
    USER = "👤"
    USERS = "👥"
    PACKAGE = "📦"
    TICKET = "🎫"
    SETTINGS = "⚙️"
    STATS = "📊"
    BROADCAST = "📢"
    AUDIT = "📋"
    ADMIN = "👮"
    LANGUAGE = "🌐"
    ABOUT = "ℹ️"

    CUSTOM_ENABLED = settings.custom_emoji_enabled
    IDS = {
        "cart": settings.emoji_cart_id,
        "apple": settings.emoji_apple_id,
        "wallet": settings.emoji_wallet_id,
        "success": settings.emoji_success_id,
        "error": settings.emoji_error_id,
        "payment": settings.emoji_payment_id,
        "support": settings.emoji_support_id,
        "profile": settings.emoji_profile_id,
        "settings": settings.emoji_settings_id,
        "order": settings.emoji_order_id,
        "inventory": settings.emoji_inventory_id,
        "back": settings.emoji_back_id,
        "cancel": settings.emoji_cancel_id,
        "gift": settings.emoji_gift_id,
    }

    @classmethod
    def custom(cls, key: str) -> str | None:
        if not cls.CUSTOM_ENABLED:
            return None
        return cls.IDS.get(key) or None
