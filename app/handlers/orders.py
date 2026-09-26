from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.order_repo import OrderRepository
from app.localization import get_text
from app.services.inventory_service import InventoryService
from app.utils.formatting import format_price
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def _get_localized_status(status: str, lang: str) -> str:
    """Return localized human-readable order status."""
    key = f"orders.status_{status.lower()}"
    # Fallback to generic status if specific key missing
    return get_text(key, lang, default=get_text("orders.status_default", lang))


async def show_user_orders(message: Message, session: AsyncSession, db_user, lang: str = "fa"):
    if not db_user:
        return
    order_repo = OrderRepository(session)
    orders = await order_repo.get_by_user(db_user.id, limit=50)
    if not orders:
        text = f"📦 {get_text('orders.empty', lang)}"
        kb = InlineKeyboardBuilder()
        kb.button(text=f"🛒 {get_text('menu.buy_apple_id', lang)}", callback_data="menu:buy")
        kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
        kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="orders:close")
        kb.adjust(1)
        await MessageCleanupService.show_screen(message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)
        return

    kb = InlineKeyboardBuilder()
    for order in orders:
        status_localized = await _get_localized_status(order.status.value, lang)
        status_emoji = "🟢" if order.status.value in ["delivered", "paid", "completed", "fulfilled"] else "🟡"
        kb.button(
            text=f"{status_emoji} #{order.id} - {status_localized}",
            callback_data=f"orders:detail:{order.id}"
        )
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="orders:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        message.chat.id,
        f"📦 {get_text('orders.title', lang)}",
        reply_markup=kb.as_markup(),
        force_new=True,
    )


@router.callback_query(F.data.startswith("orders:detail:"))
async def order_detail(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    order_id = int(callback.data.split(":")[2])
    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)

    if not order or order.user_id != db_user.id:
        await callback.answer(get_text("errors.not_found", lang), show_alert=True)
        return

    status_localized = await _get_localized_status(order.status.value, lang)
    date_str = order.created_at.strftime("%Y/%m/%d %H:%M")
    discount_str = format_price(order.discount, lang) if order.discount else format_price(0, lang)
    # Personal Apple ID orders have no catalog product — fall back to a label.
    product_label = order.product.name if order.product else get_text("products.personal", lang)

    text = (
        f"🧾 {get_text('orders.title', lang)} #{order.id}\n\n"
        f"🍏 {get_text('products.product_name', lang)}: {product_label}\n"
        f"💰 {get_text('products.price', lang)}: {format_price(order.price, lang)}\n"
        f"🏷 {get_text('orders.discount', lang)}: {discount_str}\n"
        f"💵 {get_text('products.final_price', lang)}: {format_price(order.final_price, lang)}\n"
        f"🟢 {get_text('orders.status', lang)}: {status_localized}\n"
        f"📅 {get_text('orders.created_at', lang)}: {date_str}\n"
    )

    kb = InlineKeyboardBuilder()
    if order.inventory_id and order.status.value in ["delivered", "fulfilled", "paid"]:
        kb.button(text=f"🍏 {get_text('orders.view_apple_id', lang)}", callback_data=f"orders:view_apple:{order.id}")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:purchases")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="orders:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(callback.message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)
    await callback.answer()


@router.callback_query(F.data.startswith("orders:view_apple:"))
async def view_apple_id(callback: CallbackQuery, session: AsyncSession, db_user, lang="fa"):
    order_id = int(callback.data.split(":")[2])
    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)

    if not order or order.user_id != db_user.id:
        await callback.answer(get_text("errors.not_found", lang), show_alert=True)
        return

    inventory_service = InventoryService(session)
    inventory = await inventory_service.get_by_id(order.inventory_id)
    if not inventory:
        await callback.answer(get_text("orders.apple_id_not_found", lang), show_alert=True)
        return

    account = await inventory_service.decrypt_inventory(inventory)
    fulfillment = await inventory_service.get_fulfillment_data(inventory)

    if not account:
        await callback.answer(get_text("orders.apple_id_decrypt_error", lang), show_alert=True)
        return

    field_labels = {
        "date_of_birth": "📅 Date of Birth",
        "school": "🧍‍♂️ School",
        "job": "👨‍⚕️ Job",
        "parents_meet": "🌆 Parents Meet",
    }

    text = "🍏 Apple ID\n\n"
    text += f"📧 {account.get('email', '—')}\n"
    text += f"🔑 Password: {account.get('password', '—')}\n\n"
    if fulfillment:
        for key, value in fulfillment.items():
            if key == "notes":
                continue
            label = field_labels.get(key, key.replace('_', ' ').title())
            text += f"{label}: {value}\n"
        notes = fulfillment.get("notes")
        if notes:
            text += f"\n📝 Notes: {notes}\n"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data=f"orders:detail:{order.id}")
    kb.button(text=f"✖️ {get_text('common.close', lang)}", callback_data="orders:close")
    kb.adjust(1)

    await MessageCleanupService.show_screen(callback.message.chat.id, text, reply_markup=kb.as_markup(), force_new=True)
    await callback.answer()


@router.callback_query(F.data == "orders:close")
async def orders_close(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await MessageCleanupService.close(callback.message.chat.id)
    await callback.answer(get_text("common.closed", lang))
