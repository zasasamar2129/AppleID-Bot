from __future__ import annotations

import logging
import re
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.products import product_type_keyboard
from app.database.models.enums import OrderType, ProductType
from app.localization import get_text
from app.services.inventory_service import InventoryService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.settings_service import SettingsService
from app.states.purchase import PurchaseStates
from app.utils.formatting import format_price
from app.utils.message_manager import MessageCleanupService

logger = logging.getLogger(__name__)
router = Router()


async def build_payment_keyboard(
    session: AsyncSession,
    lang: str,
) -> InlineKeyboardBuilder:
    """Build payment method buttons based on which methods are enabled in settings."""
    from app.config import settings as env_settings

    settings_service = SettingsService(session)
    methods = await settings_service.get_payment_methods()

    kb = InlineKeyboardBuilder()
    if methods.get("payment_online_enabled", True) and env_settings.is_online_payment_configured:
        kb.add(InlineKeyboardButton(text=get_text("products.payment_online", lang), callback_data="pay:online"))
    if methods.get("payment_card_enabled", True):
        kb.add(InlineKeyboardButton(text=get_text("products.payment_card", lang), callback_data="pay:card"))
    if methods.get("payment_wallet_enabled", True):
        kb.add(InlineKeyboardButton(text=get_text("products.payment_wallet", lang), callback_data="pay:wallet"))
    # Optional coupon — always offered; user may skip.
    kb.add(InlineKeyboardButton(text=get_text("coupon.apply", lang), callback_data="purchase:coupon"))
    kb.add(InlineKeyboardButton(text=get_text("common.back", lang), callback_data="purchase:back"))
    kb.adjust(1)
    return kb


@router.callback_query(F.data == "menu:buy")
async def start_purchase(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("products.select_type", lang),
        reply_markup=product_type_keyboard(lang),
        force_new=True,
    )
    await state.set_state(PurchaseStates.SELECT_TYPE)
    await callback.answer()


@router.callback_query(PurchaseStates.SELECT_TYPE, F.data.startswith("purchase:type:"))
async def select_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    ptype = callback.data.split(":")[2]
    await state.update_data(type=ptype)
    product_service = ProductService(session)

    # Both personal and ready-made products are chosen from a product list.
    product_filter = ProductType.PERSONAL if ptype == "personal" else ProductType.READY_MADE
    products = await product_service.get_active_products(product_filter)
    if not products:
        await MessageCleanupService.show_screen(
            chat_id=callback.message.chat.id,
            text=get_text("products.no_products", lang),
            force_new=True,
        )
        await state.clear()
        return

    kb = InlineKeyboardBuilder()
    for p in products:
        price_str = format_price(p.price, lang)
        kb.add(InlineKeyboardButton(
            text=f"{p.name} - {price_str}",
            callback_data=f"purchase:product:{p.id}"
        ))
    kb.add(InlineKeyboardButton(text=get_text("common.back", lang), callback_data="menu:main"))
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("products.choose_product", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await state.set_state(PurchaseStates.SELECT_PRODUCT)
    await callback.answer()


@router.callback_query(PurchaseStates.SELECT_PRODUCT, F.data.startswith("purchase:product:"))
async def select_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    product_service = ProductService(session)
    product = await product_service.get_product(product_id)
    if not product:
        await callback.message.edit_text(get_text("products.not_found", lang))
        await state.clear()
        return

    await state.update_data(product_id=product.id)

    # For PERSONAL products: collect user info first, then create the order
    # after review confirms. No inventory reservation.
    if product.type == ProductType.PERSONAL:
        await callback.message.edit_text(
            get_text("products.personal_first_name", lang),
            reply_markup=cancel_keyboard("menu:main", lang)
        )
        await state.set_state(PurchaseStates.COLLECT_FIRST_NAME)
        await callback.answer()
        return

    # Ready-made flow: reserve inventory, create order immediately.
    inventory_id = None
    inventory_service = InventoryService(session)
    inventory = await inventory_service.get_available_for_product(product.id)
    if not inventory:
        await callback.message.edit_text(get_text("products.out_of_stock", lang))
        await state.clear()
        return
    reserved_inv = await inventory_service.reserve_inventory(inventory.id)
    if not reserved_inv:
        await callback.message.edit_text(get_text("products.out_of_stock", lang))
        await state.clear()
        return
    inventory_id = reserved_inv.id

    # Convert product type to order type
    order_type = OrderType(product.type.value.upper())

    # Create order
    order_service = OrderService(session)
    order = await order_service.create_order(
        user_id=db_user.id,
        product_id=product.id,
        order_type=order_type,
        price=product.price,
        discount=product.discount or Decimal("0"),
        final_price=product.price - (product.discount or Decimal("0")),
        currency=product.currency,
        customer_information=None,
        inventory_id=inventory_id,
    )

    await state.update_data(order_id=order.id, product_id=product.id)

    # Show payment methods (only the enabled ones)
    kb = await build_payment_keyboard(session, lang)

    text = (
        f"{get_text('products.product_name', lang, name=product.name)}\n"
        f"{get_text('products.price', lang, price=format_price(product.price, lang))}\n"
    )
    if product.description:
        text += f"{product.description}\n"
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await state.set_state(PurchaseStates.SELECT_PAYMENT)
    await callback.answer()


# Personal Apple ID flow remains unchanged (but included for completeness)
@router.message(PurchaseStates.COLLECT_FIRST_NAME)
async def first_name(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(first_name=message.text.strip())
    await message.delete()
    await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("products.personal_last_name", lang),
        reply_markup=cancel_keyboard("menu:main", lang),
    )
    await state.set_state(PurchaseStates.COLLECT_LAST_NAME)


@router.message(PurchaseStates.COLLECT_LAST_NAME)
async def last_name(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(last_name=message.text.strip())
    await message.delete()
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=get_text("confirm.yes", lang), callback_data="email:yes"))
    kb.add(InlineKeyboardButton(text=get_text("confirm.no", lang), callback_data="email:no"))
    kb.add(InlineKeyboardButton(text=get_text("common.back", lang), callback_data="purchase:back"))
    await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("products.personal_email_ask", lang),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(PurchaseStates.COLLECT_EMAIL_ASK)


@router.callback_query(PurchaseStates.COLLECT_EMAIL_ASK, F.data.startswith("email:"))
async def email_ask(callback: CallbackQuery, state: FSMContext, lang="fa"):
    if callback.data == "email:yes":
        await callback.message.edit_text(
            get_text("products.personal_email", lang),
            reply_markup=cancel_keyboard("menu:main", lang)
        )
        await state.set_state(PurchaseStates.COLLECT_EMAIL)
    else:
        await state.update_data(email=None)
        await MessageCleanupService.send_temporary(
            callback.message.chat.id,
            get_text("products.personal_phone", lang),
            reply_markup=cancel_keyboard("menu:main", lang),
        )
        await state.set_state(PurchaseStates.COLLECT_PHONE)
    await callback.answer()


@router.message(PurchaseStates.COLLECT_EMAIL)
async def email(message: Message, state: FSMContext, lang="fa"):
    email = message.text.strip()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await message.answer(get_text("errors.invalid_email", lang))
        return
    await state.update_data(email=email)
    await message.delete()
    await MessageCleanupService.send_temporary(
        message.chat.id,
        get_text("products.personal_phone", lang),
        reply_markup=cancel_keyboard("menu:main", lang),
    )
    await state.set_state(PurchaseStates.COLLECT_PHONE)


@router.message(PurchaseStates.COLLECT_PHONE)
async def phone(message: Message, state: FSMContext, lang="fa"):
    phone = message.text.strip()
    if not re.match(r"^\+?[\d\s\-]{7,15}$", phone):
        await message.answer(get_text("errors.invalid_phone", lang))
        return
    await state.update_data(phone=phone)
    await message.delete()
    data = await state.get_data()
    review_text = (
        f"📋 {get_text('products.review', lang)}\n\n"
        f"👤 {get_text('products.first_name', lang)}: {data['first_name']}\n"
        f"👤 {get_text('products.last_name', lang)}: {data['last_name']}\n"
        f"📧 {get_text('products.email', lang)}: {data.get('email') or '—'}\n"
        f"📱 {get_text('products.phone', lang)}: {data['phone']}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=get_text("products.confirm_continue", lang), callback_data="review:confirm"))
    kb.add(InlineKeyboardButton(text=get_text("products.edit", lang), callback_data="review:edit"))
    kb.add(InlineKeyboardButton(text=get_text("common.cancel", lang), callback_data="menu:main"))
    kb.adjust(1)
    await MessageCleanupService.send_temporary(message.chat.id, review_text, reply_markup=kb.as_markup())
    await state.set_state(PurchaseStates.REVIEW_ORDER)


@router.callback_query(PurchaseStates.REVIEW_ORDER, F.data == "review:confirm")
async def review_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user, lang="fa"):
    data = await state.get_data()
    order_service = OrderService(session)

    # Load the selected personal product
    product_service = ProductService(session)
    product_id = data.get("product_id")
    product = await product_service.get_product(product_id) if product_id else None
    if not product:
        await callback.answer(get_text("products.not_found", lang), show_alert=True)
        await state.clear()
        return

    price = product.price
    discount = (product.discount or Decimal("0"))
    final_price = price - discount

    order = await order_service.create_order(
        user_id=db_user.id,
        product_id=product.id,
        order_type=OrderType.PERSONAL,
        price=price,
        discount=discount,
        final_price=final_price,
        currency=product.currency or "IRR",
        customer_information={
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
        },
        inventory_id=None,
    )

    await state.update_data(order_id=order.id, product_id=product.id)

    # Show payment methods for Personal Apple ID order (only enabled ones)
    kb = await build_payment_keyboard(session, lang)

    text = (
        f"{get_text('products.product_name', lang, name=product.name)}\n"
        f"{get_text('products.price', lang, price=format_price(price, lang))}\n"
    )
    if product.description:
        text += f"{product.description}\n"
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await state.set_state(PurchaseStates.SELECT_PAYMENT)
    await callback.answer()


@router.callback_query(PurchaseStates.REVIEW_ORDER, F.data == "review:edit")
async def review_edit(callback: CallbackQuery, state: FSMContext, lang="fa"):
    # Go back to collecting first name
    await callback.message.edit_text(
        get_text("products.personal_first_name", lang),
        reply_markup=cancel_keyboard("menu:main", lang)
    )
    await state.set_state(PurchaseStates.COLLECT_FIRST_NAME)
    await callback.answer()


@router.callback_query(F.data == "purchase:back")
async def purchase_back(callback: CallbackQuery, state: FSMContext, lang="fa"):
    current_state = await state.get_state()
    if current_state == PurchaseStates.SELECT_PRODUCT.state:
        await start_purchase(callback, state, lang)
    else:
        await state.clear()
        await callback.message.edit_text(get_text("start.main_menu", lang), reply_markup=main_menu_keyboard(lang))
    await callback.answer()
