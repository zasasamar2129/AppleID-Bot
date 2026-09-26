from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.services.price_inquiry_service import PriceInquiryService
from app.states.admin.price_inquiry import AdminPriceInquiryStates
from app.utils.formatting import format_price

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


@router.callback_query(F.data == "admin:price_inquiry")
async def admin_price_inquiry_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    service = PriceInquiryService(session)
    items = await service.get_all_items()
    if not items:
        text = "💰 Price Inquiry\n\nNo services yet."
    else:
        text = "💰 Price Inquiry\n\n"
        for item in items:
            status = "🟢" if item.is_active else "🔴"
            name = item.name_fa if lang == "fa" else item.name_en
            text += f"{status} {name} - {format_price(item.price, lang)}\n"

    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=f"{item.name_fa}", callback_data=f"admin:price_inquiry:item:{item.id}")
    kb.button(text="➕ Add Service", callback_data="admin:price_inquiry:add")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:price_inquiry:add")
async def add_service_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.edit_text("Enter service name in Persian:")
    await state.set_state(AdminPriceInquiryStates.NAME_FA)
    await callback.answer()


@router.message(AdminPriceInquiryStates.NAME_FA)
async def process_name_fa(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(name_fa=message.text.strip())
    await message.answer("Enter service name in English:")
    await state.set_state(AdminPriceInquiryStates.NAME_EN)


@router.message(AdminPriceInquiryStates.NAME_EN)
async def process_name_en(message: Message, state: FSMContext, lang="fa"):
    await state.update_data(name_en=message.text.strip())
    await message.answer("Enter price (number):")
    await state.set_state(AdminPriceInquiryStates.PRICE)


@router.message(AdminPriceInquiryStates.PRICE)
async def process_price(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        price = Decimal(message.text.strip())
        if price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Invalid price. Please enter a positive number.")
        return
    data = await state.get_data()
    service = PriceInquiryService(session)
    await service.create_item(
        name_fa=data["name_fa"],
        name_en=data["name_en"],
        price=price,
    )
    await message.answer("✅ Service added.")
    await state.clear()


@router.callback_query(F.data.startswith("admin:price_inquiry:item:"))
async def admin_service_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    item_id = int(callback.data.split(":")[3])
    service = PriceInquiryService(session)
    item = await service.repo.get_by_id(item_id)
    if not item:
        await callback.answer("Service not found", show_alert=True)
        return
    text = (
        f"{item.name_fa} ({item.name_en})\n"
        f"Price: {format_price(item.price, lang)}\n"
        f"Active: {'Yes' if item.is_active else 'No'}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Edit", callback_data=f"admin:price_inquiry:edit:{item.id}")
    kb.button(text="🔴 Deactivate" if item.is_active else "🟢 Activate", callback_data=f"admin:price_inquiry:toggle:{item.id}")
    kb.button(text="🗑 Delete", callback_data=f"admin:price_inquiry:delete:{item.id}")
    kb.button(text="⬅️ Back", callback_data="admin:price_inquiry")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:price_inquiry:edit:"))
async def edit_service_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    item_id = int(callback.data.split(":")[3])
    await state.update_data(item_id=item_id)
    await callback.message.edit_text("Enter new price:")
    await state.set_state(AdminPriceInquiryStates.EDIT_PRICE)
    await callback.answer()


@router.message(AdminPriceInquiryStates.EDIT_PRICE)
async def process_edit_price(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        new_price = Decimal(message.text.strip())
        if new_price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Invalid price.")
        return
    data = await state.get_data()
    item_id = data["item_id"]
    service = PriceInquiryService(session)
    await service.update_item(item_id, {"price": new_price})
    await message.answer("✅ Price updated.")
    await state.clear()


@router.callback_query(F.data.startswith("admin:price_inquiry:toggle:"))
async def toggle_service(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    item_id = int(callback.data.split(":")[3])
    service = PriceInquiryService(session)
    item = await service.repo.get_by_id(item_id)
    if item:
        await service.update_item(item_id, {"is_active": not item.is_active})
    await callback.answer("Status changed", show_alert=True)
    await admin_price_inquiry_menu(callback, session, lang)


@router.callback_query(F.data.startswith("admin:price_inquiry:delete:"))
async def delete_service(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    item_id = int(callback.data.split(":")[3])
    service = PriceInquiryService(session)
    await service.delete_item(item_id)
    await callback.answer("Service deleted", show_alert=True)
    await admin_price_inquiry_menu(callback, session, lang)
