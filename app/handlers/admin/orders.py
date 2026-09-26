from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.order_repo import OrderRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.states.admin.order import AdminOrderStates
from app.utils.formatting import format_price

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


@router.callback_query(F.data == "admin:orders")
async def orders_list(callback: CallbackQuery, session: AsyncSession, page: int = 1, lang="fa"):
    order_repo = OrderRepository(session)
    total_orders = await order_repo.count()
    per_page = 10
    pages = max(1, (total_orders + per_page - 1) // per_page)
    orders = await order_repo.get_all(limit=per_page, offset=(page - 1) * per_page)
    if not orders:
        await callback.message.edit_text("No orders found.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.button(text=f"Order #{o.id} - {o.status.value}", callback_data=f"admin:order:{o.id}")

    if page > 1:
        kb.button(text="⬅️ Previous", callback_data=f"admin:orders:page:{page-1}")
    kb.button(text=f"{page}/{pages}", callback_data="noop")
    if page < pages:
        kb.button(text="Next ➡️", callback_data=f"admin:orders:page:{page+1}")

    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text("🧾 Orders", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:orders:page:"))
async def orders_page(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    page = int(callback.data.split(":")[3])
    await orders_list(callback, session, page, lang)


@router.callback_query(F.data.startswith("admin:order:"))
async def order_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    order_id = int(callback.data.split(":")[2])
    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    if not order:
        await callback.answer("Order not found", show_alert=True)
        return

    # Personal Apple ID orders have no linked catalog product.
    product_label = order.product.name if order.product else "Personal Apple ID"
    order_type_label = order.order_type.value.upper()
    text = (
        f"🧾 Order #{order.id}\n\n"
        f"User: {order.user.first_name} {order.user.last_name or ''}\n"
        f"Type: {order_type_label}\n"
        f"Product: {product_label}\n"
        f"Price: {format_price(order.price, lang)}\n"
        f"Final: {format_price(order.final_price, lang)}\n"
        f"Status: {order.status.value}\n"
    )

    # Show customer-entered information (name, email, phone, etc.)
    if order.customer_information:
        text += "\n👤 Customer Info:\n"
        try:
            info = json.loads(order.customer_information) if isinstance(order.customer_information, str) else order.customer_information
        except (ValueError, TypeError):
            info = {}
        for key, value in info.items():
            if value:
                text += f"  {key}: {value}\n"

    kb = InlineKeyboardBuilder()
    if order.status.value not in ["delivered", "refunded"]:
        kb.button(text="🗑 Delete Order", callback_data=f"admin:delete_order:{order.id}")
    kb.button(text="⬅️ Back", callback_data="admin:orders")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:delete_order:"))
async def delete_order_confirm(callback: CallbackQuery, state: FSMContext, lang="fa"):
    order_id = int(callback.data.split(":")[2])
    await state.update_data(delete_order_id=order_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Yes, delete", callback_data="admin:confirm_delete_order")
    kb.button(text="❌ No", callback_data="admin:cancel_delete_order")
    kb.adjust(1)
    await callback.message.edit_text(
        get_text("admin.orders.delete_confirm", lang),
        reply_markup=kb.as_markup()
    )
    await state.set_state(AdminOrderStates.CONFIRM_DELETE)
    await callback.answer()


@router.callback_query(AdminOrderStates.CONFIRM_DELETE, F.data == "admin:confirm_delete_order")
async def confirm_delete_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    order_id = data.get("delete_order_id")
    if not order_id:
        await callback.answer("No order selected", show_alert=True)
        await state.clear()
        return

    order_repo = OrderRepository(session)
    order = await order_repo.get_by_id(order_id)
    if not order:
        await callback.answer("Order not found", show_alert=True)
        await state.clear()
        return

    # Release inventory if reserved
    if order.inventory_id:
        inventory_repo = InventoryRepository(session)
        inventory = await inventory_repo.get_by_id(order.inventory_id)
        if inventory and inventory.status.value == "reserved":
            await inventory_repo.release_reservation(order.inventory_id)

    await session.delete(order)
    await session.commit()

    audit = AuditService(session)
    await audit.log(
        admin_telegram_id=callback.from_user.id,
        action="delete_order",
        target_type="order",
        target_id=str(order_id),
    )

    await callback.message.edit_text(get_text("admin.orders.deleted", lang, order_id=order_id))
    await state.clear()
    await callback.answer()


@router.callback_query(AdminOrderStates.CONFIRM_DELETE, F.data == "admin:cancel_delete_order")
async def cancel_delete_order(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await callback.message.edit_text(get_text("admin.orders.delete_cancelled", lang))
    await callback.answer()
