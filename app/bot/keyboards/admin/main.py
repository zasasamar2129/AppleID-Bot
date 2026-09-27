from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.localization import get_text


def admin_main_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    # Main admin sections (two columns)
    sections = [
        ("admin.dashboard", "admin:dashboard"),
        ("admin.users", "admin:users"),
        ("admin.products", "admin:products"),
        ("admin.inventory", "admin:inventory"),
        ("admin.orders", "admin:orders"),
        ("admin.payments", "admin:payments"),
        ("admin.wallet", "admin:wallet"),
        ("admin.coupons", "admin:coupons"),
        ("admin.broadcast", "admin:broadcast"),
        ("admin.support", "admin:support"),
        ("admin.referrals", "admin:referrals"),
        ("admin.statistics", "admin:statistics"),
        ("admin.settings", "admin:settings"),
        ("admin.admins", "admin:admins"),
        ("unlock_admin.title", "admin:unlock_requests"),
    ]

    for key, callback in sections:
        kb.add(InlineKeyboardButton(
            text=get_text(key, lang),
            callback_data=callback,
            style="primary"
        ))

    # Audit Logs (separate, full width)
    kb.add(InlineKeyboardButton(
        text=get_text("admin.audit", lang),
        callback_data="admin:audit",
        style="primary"
    ))

    # Scheduler health (full width) — admins only, never shown to customers.
    kb.add(InlineKeyboardButton(
        text="🛠 Scheduler Health",
        callback_data="admin:scheduler_health",
        style="primary"
    ))

    # Back and Close stacked vertically
    kb.add(InlineKeyboardButton(
        text=get_text("common.back", lang),
        callback_data="admin:main_back"
    ))
    kb.add(InlineKeyboardButton(
        text=get_text("common.close", lang),
        callback_data="admin:close",
        style="danger"
    ))

    # Layout: two columns for sections, then single column for audit,
    # scheduler health, back, close
    kb.adjust(2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1)
    return kb.as_markup()
