from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin.main import admin_main_keyboard
from app.config import settings
from app.localization import get_text
from app.services.statistics_service import StatisticsService
from app.utils.formatting import format_price
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
async def admin_command(message: Message, lang="fa"):
    if message.from_user.id in settings.admin_ids_list:
        await message.answer(
            get_text("admin.panel", lang),
            reply_markup=admin_main_keyboard(lang)
        )
    else:
        await message.answer(get_text("errors.unauthorized", lang))


@router.callback_query(F.data == "admin:main", IsAdmin())
async def admin_main_menu(callback: CallbackQuery, lang="fa"):
    # Add a note/welcome line to the panel
    panel_text = get_text("admin.panel", lang) + "\n\n" + get_text("admin.panel_note", lang)
    await callback.message.edit_text(
        panel_text,
        reply_markup=admin_main_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard", IsAdmin())
async def admin_dashboard(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    stats_service = StatisticsService(session)
    stats = await stats_service.get_dashboard_stats("all")
    text = f"📊 {get_text('admin.dashboard', lang)}\n\n"
    text += f"{get_text('admin.dashboard.total_users', lang)}: {stats['total_users']}\n"
    text += f"{get_text('admin.dashboard.total_orders', lang)}: {stats['total_orders']}\n"
    text += f"{get_text('admin.dashboard.completed_orders', lang)}: {stats['completed_orders']}\n"
    text += f"{get_text('admin.dashboard.pending_orders', lang)}: {stats['pending_orders']}\n"
    text += f"{get_text('admin.dashboard.cancelled_orders', lang)}: {stats['cancelled_orders']}\n"
    text += f"{get_text('admin.dashboard.revenue', lang)}: {format_price(stats['revenue'], lang)}\n"
    text += f"{get_text('admin.dashboard.available_inventory', lang)}: {stats['available_inventory']}\n"
    text += f"{get_text('admin.dashboard.reserved_inventory', lang)}: {stats['reserved_inventory']}\n"
    text += f"{get_text('admin.dashboard.sold_inventory', lang)}: {stats['sold_inventory']}\n"
    text += f"{get_text('admin.dashboard.pending_payments', lang)}: {stats['pending_payments']}\n"
    text += f"{get_text('admin.dashboard.open_tickets', lang)}: {stats['open_tickets']}\n"
    await callback.message.edit_text(text)
    await callback.answer()


import json
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from app.bot.bot import redis_client

@router.callback_query(F.data == "admin:logs", IsAdmin())
async def admin_logs(callback: CallbackQuery, lang="fa"):
    try:
        logs_raw = await redis_client.lrange("bot:logs", 0, 19)
        if not logs_raw:
            await callback.message.edit_text(
                "📜 *Bot Logs*\n\nNo logs recorded yet.",
                parse_mode="Markdown",
                reply_markup=admin_logs_keyboard()
            )
            await callback.answer()
            return

        text = "📜 *Recent Bot Logs (Top 20)*\n\n"
        for log_str in reversed(logs_raw):
            try:
                log = json.loads(log_str)
                level_emoji = "🟢" if log["level"] == "INFO" else ("🟡" if log["level"] == "WARNING" else "🔴")
                time_str = log['timestamp'].split('T')[1].split('.')[0]
                text += f"{level_emoji} `[{time_str}]` *{log['level']}* ({log['name']}):\n```{log['message']}```\n\n"
            except Exception:
                pass

        if len(text) > 4000:
            text = text[:3900] + "\n\n..._truncated due to message size limit_"

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=admin_logs_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        await callback.answer("Error fetching logs", show_alert=True)

    await callback.answer()

def admin_logs_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="🔄 Refresh", callback_data="admin:logs"))
    kb.add(InlineKeyboardButton(text="⬅️ Back", callback_data="admin:main"))
    kb.adjust(1)
    return kb.as_markup()
@router.callback_query(F.data == "admin:close", IsAdmin())
async def admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.debug("Failed to delete admin panel message: %s", e)
    await callback.answer("Closed")


# Back handler (optional, returns to main user menu or previous)
@router.callback_query(F.data == "admin:main_back", IsAdmin())
async def admin_back(callback: CallbackQuery, state: FSMContext):
    # For now, close the admin panel and return to main user menu
    await state.clear()
    from app.bot.keyboards.main_menu import main_menu_keyboard
    from app.localization import get_text
    await MessageCleanupService.show_screen(
        callback.message.chat.id,
        get_text("start.welcome", "fa", name=callback.from_user.first_name),
        reply_markup=main_menu_keyboard("fa")
    )
    await callback.answer()
