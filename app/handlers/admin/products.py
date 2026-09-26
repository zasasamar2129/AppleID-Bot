from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.enums import ProductType
from app.localization import get_text
from app.services.product_service import ProductService
from app.states.admin.product import AdminProductStates
from app.utils.formatting import format_price

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:products")
async def admin_products_menu(callback: CallbackQuery, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text=get_text("admin.products.create", lang), callback_data="admin:products:create")
    kb.button(text=get_text("admin.products.list", lang), callback_data="admin:products:list")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text(get_text("admin.products", lang), reply_markup=kb.as_markup())
    await callback.answer()


# ---------- Create product ----------
@router.callback_query(F.data == "admin:products:create")
async def admin_products_create(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.answer(get_text("admin.products.prompt_name", lang))
    await state.set_state(AdminProductStates.CREATE_NAME)
    await callback.answer()


@router.message(AdminProductStates.CREATE_NAME)
async def admin_products_name(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(name=message.text)
    await message.answer(get_text("admin.products.prompt_type", lang))
    await state.set_state(AdminProductStates.CREATE_TYPE)


@router.message(AdminProductStates.CREATE_TYPE)
async def admin_products_type(message: Message, state: FSMContext, lang="fa"):
    try:
        ptype = ProductType(message.text.lower())
    except ValueError:
        await message.answer(get_text("admin.products.invalid_type", lang))
        return
    await state.update_data(type=ptype)
    await message.answer(get_text("admin.products.prompt_price", lang))
    await state.set_state(AdminProductStates.CREATE_PRICE)


@router.message(AdminProductStates.CREATE_PRICE)
async def admin_products_price(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        price = Decimal(message.text.strip())
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(get_text("admin.products.invalid_price", lang))
        return
    data = await state.get_data()
    product_service = ProductService(session)
    product = await product_service.create_product({
        "name": data["name"],
        "type": data["type"],
        "price": price,
        "currency": "IRR",
    })
    await message.answer(get_text("admin.products.created", lang, product_id=product.id))
    await state.clear()


# ---------- List products ----------
@router.callback_query(F.data == "admin:products:list")
async def admin_products_list(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    product_service = ProductService(session)
    products = await product_service.product_repo.get_all(include_inactive=True)
    if not products:
        await callback.message.edit_text(get_text("admin.products.none", lang, default="No products found."))
        await callback.answer()
        return

    text = f"📦 {get_text('admin.products', lang)}\n\n"
    kb = InlineKeyboardBuilder()
    for p in products:
        status = "🟢" if p.is_active else "🔴"
        ptype = p.type.value if hasattr(p.type, "value") else str(p.type)
        text += f"{status} {p.name} ({ptype}) - {format_price(p.price, lang)}\n"
        kb.button(text=f"✏️ {p.name}", callback_data=f"admin:prodedit:{p.id}")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="admin:products")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prodedit:"))
async def admin_product_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    product_service = ProductService(session)
    product = await product_service.get_product(product_id)
    if not product:
        await callback.answer(get_text("admin.products.not_found", lang, default="Product not found"), show_alert=True)
        return

    await state.update_data(product_id=product.id)
    status = "🟢" if product.is_active else "🔴"
    text = (
        f"📦 {product.name}\n"
        f"Type: {product.type.value}\n"
        f"Price: {format_price(product.price, lang)}\n"
        f"Status: {status}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 " + get_text("admin.products.edit_price", lang, default="Edit Price"), callback_data="admin:prodedit_price")
    kb.button(text="✏️ " + get_text("admin.products.edit_name", lang, default="Edit Name"), callback_data="admin:prodedit_name")
    kb.button(text="🔄 Toggle Active", callback_data=f"admin:prodtoggle:{product_id}")
    kb.button(text="🗑 " + get_text("admin.products.delete", lang, default="Delete"), callback_data=f"admin:proddelete:{product_id}")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="admin:products:list")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:prodedit_price")
async def admin_product_edit_price_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.edit_text(get_text("admin.products.prompt_price", lang))
    await state.set_state(AdminProductStates.EDIT_PRICE)
    await callback.answer()


@router.message(AdminProductStates.EDIT_PRICE)
async def admin_product_edit_price(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        price = Decimal(message.text.strip())
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(get_text("admin.products.invalid_price", lang))
        return
    data = await state.get_data()
    product_id = data["product_id"]
    product_service = ProductService(session)
    await product_service.update_product(product_id, {"price": price})
    await message.answer(get_text("admin.products.price_updated", lang, default="✅ Price updated."))
    await state.clear()


@router.callback_query(F.data == "admin:prodedit_name")
async def admin_product_edit_name_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.edit_text(get_text("admin.products.prompt_name", lang))
    await state.set_state(AdminProductStates.EDIT_NAME)
    await callback.answer()


@router.message(AdminProductStates.EDIT_NAME)
async def admin_product_edit_name(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    product_id = data["product_id"]
    product_service = ProductService(session)
    await product_service.update_product(product_id, {"name": message.text.strip()})
    await message.answer(get_text("admin.products.name_updated", lang, default="✅ Name updated."))
    await state.clear()


@router.callback_query(F.data.startswith("admin:prodtoggle:"))
async def admin_product_toggle(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    product_service = ProductService(session)
    product = await product_service.get_product(product_id)
    if not product:
        await callback.answer(get_text("admin.products.not_found", lang, default="Product not found"), show_alert=True)
        return
    await product_service.update_product(product_id, {"is_active": not product.is_active})
    await callback.answer("Status changed", show_alert=True)
    # Re-render the edit screen for the same product.
    await state.update_data(product_id=product.id)
    callback.data = f"admin:prodedit:{product_id}"
    await admin_product_edit(callback, state, session, lang)


# ---------- Delete product ----------
@router.callback_query(F.data.startswith("admin:proddelete:"))
async def admin_product_delete_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    product_service = ProductService(session)
    product = await product_service.get_product(product_id)
    if not product:
        await callback.answer(get_text("admin.products.not_found", lang, default="Product not found"), show_alert=True)
        return

    # Check whether deletion is safe (no orders referencing this product).
    order_count = await product_service.product_repo.count_orders(product_id)
    if order_count > 0:
        await callback.answer(
            get_text(
                "admin.products.delete_has_orders",
                lang,
                count=order_count,
                default=f"Cannot delete: {order_count} order(s) reference this product. Deactivate it instead.",
            ),
            show_alert=True,
        )
        return

    await state.update_data(delete_product_id=product_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ " + get_text("confirm.yes", lang, default="Yes"), callback_data="admin:proddelete_confirm")
    kb.button(text="❌ " + get_text("confirm.no", lang, default="No"), callback_data="admin:proddelete_cancel")
    kb.adjust(1)
    await callback.message.edit_text(
        get_text("admin.products.delete_confirm", lang, default="⚠️ Are you sure you want to delete this product? Its inventory will also be removed. This cannot be undone."),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(AdminProductStates.CONFIRM_DELETE)
    await callback.answer()


@router.callback_query(AdminProductStates.CONFIRM_DELETE, F.data == "admin:proddelete_confirm")
async def admin_product_delete_do(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    product_id = data.get("delete_product_id")
    if not product_id:
        await callback.answer(get_text("admin.products.not_found", lang, default="No product selected"), show_alert=True)
        await state.clear()
        return

    product_service = ProductService(session)
    deleted, order_count = await product_service.delete_product(product_id)
    if not deleted:
        await callback.answer(
            get_text(
                "admin.products.delete_has_orders",
                lang,
                count=order_count,
                default=f"Cannot delete: {order_count} order(s) reference this product.",
            ),
            show_alert=True,
        )
        await state.clear()
        return

    await state.clear()
    await callback.message.edit_text(get_text("admin.products.deleted", lang, default="✅ Product deleted."))
    await callback.answer()


@router.callback_query(AdminProductStates.CONFIRM_DELETE, F.data == "admin:proddelete_cancel")
async def admin_product_delete_cancel(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await callback.message.edit_text(get_text("admin.products.delete_cancelled", lang, default="❌ Deletion cancelled."))
    await callback.answer()