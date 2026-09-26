from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.enums import CouponType
from app.services.coupon_service import CouponService
from app.states.admin.coupon import AdminCouponStates

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


def _coupon_label(coupon) -> str:
    if coupon.type.value == "percentage":
        return f"{coupon.value}%"
    return f"{coupon.value} تومان"


def _coupon_type_enum(type_str: str) -> CouponType:
    """Map a UI type string to the CouponType enum (SAEnum uses member NAME)."""
    return CouponType.PERCENTAGE if type_str == "percentage" else CouponType.FIXED


@router.callback_query(F.data == "admin:coupons")
async def admin_coupons_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    coupon_service = CouponService(session)
    coupons = await coupon_service.get_all_coupons()

    kb = InlineKeyboardBuilder()
    if not coupons:
        text = "🎟 Coupon Management\n\n(No coupons yet.)"
    else:
        text = "🎟 Coupon Management\n\n"
        for c in coupons:
            status = "🟢" if c.is_active else "🔴"
            type_label = "%" if c.type.value == "percentage" else "Toman"
            text += f"{status} `{c.code}` | {c.value}{type_label} | used {c.usage_count}\n"
            kb.button(text=f"{status} {c.code}", callback_data=f"admin:coupon:view:{c.id}")
        kb.adjust(2)

    kb.button(text="➕ Create", callback_data="admin:coupon:create")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1 if coupons else 2)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:coupon:create")
async def admin_coupon_create_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.edit_text("Enter the coupon code (e.g. SALE10):")
    await state.set_state(AdminCouponStates.CREATE_CODE)
    await callback.answer()


@router.message(AdminCouponStates.CREATE_CODE)
async def admin_coupon_code(message: Message, state: FSMContext, lang="fa"):
    code = message.text.strip().upper()
    if not code:
        await message.answer("Code cannot be empty.")
        return
    await state.update_data(coupon_code=code)
    kb = InlineKeyboardBuilder()
    kb.button(text="Percentage %", callback_data="admin:coupon:type:percentage")
    kb.button(text="Fixed (Toman)", callback_data="admin:coupon:type:fixed")
    kb.adjust(2)
    await message.answer(f"Code: `{code}`\n\nChoose discount type:", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_TYPE)
    await message.delete()


@router.callback_query(AdminCouponStates.CREATE_TYPE, F.data.startswith("admin:coupon:type:"))
async def admin_coupon_type(callback: CallbackQuery, state: FSMContext, lang="fa"):
    ctype = callback.data.split(":")[3]
    await state.update_data(coupon_type=ctype)
    await callback.message.edit_text(
        "Enter the discount value:\n"
        "- percentage: e.g. 10 (means 10%)\n"
        "- fixed: e.g. 50000 (means 50,000 Toman)"
    )
    await state.set_state(AdminCouponStates.CREATE_VALUE)
    await callback.answer()


@router.message(AdminCouponStates.CREATE_VALUE)
async def admin_coupon_value(message: Message, state: FSMContext, lang="fa"):
    try:
        value = Decimal(message.text.strip())
        if value <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Invalid value. Enter a positive number.")
        return
    await state.update_data(coupon_value=str(value))
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip", callback_data="admin:coupon:skip_max")
    kb.adjust(1)
    await message.answer("Optional: max discount (enter number, or Skip):", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_MAX_DISCOUNT)
    await message.delete()


@router.callback_query(AdminCouponStates.CREATE_MAX_DISCOUNT, F.data == "admin:coupon:skip_max")
async def admin_coupon_skip_max(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.update_data(coupon_max_discount=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip", callback_data="admin:coupon:skip_min")
    kb.adjust(1)
    await callback.message.edit_text("Optional: minimum order amount (number), or Skip:", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_MIN_ORDER)
    await callback.answer()


@router.message(AdminCouponStates.CREATE_MAX_DISCOUNT)
async def admin_coupon_max(message: Message, state: FSMContext, lang="fa"):
    try:
        val = Decimal(message.text.strip())
        if val < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Invalid. Enter a non-negative number or Skip.")
        return
    await state.update_data(coupon_max_discount=str(val))
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip", callback_data="admin:coupon:skip_min")
    kb.adjust(1)
    await message.answer("Optional: minimum order amount (number), or Skip:", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_MIN_ORDER)
    await message.delete()


@router.callback_query(AdminCouponStates.CREATE_MIN_ORDER, F.data == "admin:coupon:skip_min")
async def admin_coupon_skip_min(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.update_data(coupon_min_order=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip", callback_data="admin:coupon:skip_global")
    kb.adjust(1)
    await callback.message.edit_text("Optional: global usage limit (number), or Skip:", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_GLOBAL_LIMIT)
    await callback.answer()


@router.message(AdminCouponStates.CREATE_MIN_ORDER)
async def admin_coupon_min(message: Message, state: FSMContext, lang="fa"):
    try:
        val = Decimal(message.text.strip())
        if val < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Invalid. Enter a non-negative number or Skip.")
        return
    await state.update_data(coupon_min_order=str(val))
    kb = InlineKeyboardBuilder()
    kb.button(text="Skip", callback_data="admin:coupon:skip_global")
    kb.adjust(1)
    await message.answer("Optional: global usage limit (number), or Skip:", reply_markup=kb.as_markup())
    await state.set_state(AdminCouponStates.CREATE_GLOBAL_LIMIT)
    await message.delete()


@router.callback_query(AdminCouponStates.CREATE_GLOBAL_LIMIT, F.data == "admin:coupon:skip_global")
async def admin_coupon_skip_global(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    await state.update_data(coupon_global_limit=None, coupon_per_user_limit=1)
    data = await state.get_data()
    coupon_value = data.get("coupon_value") or "0"
    await state.clear()
    coupon_service = CouponService(session)
    coupon = await coupon_service.create_coupon({
        "code": data.get("coupon_code"),
        "type": _coupon_type_enum(data.get("coupon_type")),
        "value": Decimal(coupon_value),
        "max_discount": Decimal(data["coupon_max_discount"]) if data.get("coupon_max_discount") else None,
        "min_order_amount": Decimal(data["coupon_min_order"]) if data.get("coupon_min_order") else None,
        "global_usage_limit": data.get("coupon_global_limit"),
        "per_user_limit": 1,
        "is_active": True,
    })
    await callback.message.edit_text(f"✅ Coupon `{coupon.code}` created ({_coupon_label(coupon)}).")
    await callback.answer()


@router.message(AdminCouponStates.CREATE_GLOBAL_LIMIT)
async def admin_coupon_global(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    try:
        val = int(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("Invalid. Enter a non-negative integer or Skip.")
        return
    await state.update_data(coupon_global_limit=val, coupon_per_user_limit=1)
    data = await state.get_data()
    coupon_value = data.get("coupon_value") or "0"
    await state.clear()
    coupon_service = CouponService(session)
    coupon = await coupon_service.create_coupon({
        "code": data.get("coupon_code"),
        "type": _coupon_type_enum(data.get("coupon_type")),
        "value": Decimal(coupon_value),
        "max_discount": Decimal(data["coupon_max_discount"]) if data.get("coupon_max_discount") else None,
        "min_order_amount": Decimal(data["coupon_min_order"]) if data.get("coupon_min_order") else None,
        "global_usage_limit": data.get("coupon_global_limit"),
        "per_user_limit": 1,
        "is_active": True,
    })
    await message.answer(f"✅ Coupon `{coupon.code}` created ({_coupon_label(coupon)}).")
    await message.delete()
    await state.clear()


@router.callback_query(F.data.startswith("admin:coupon:view:"))
async def admin_coupon_view(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    coupon_id = int(callback.data.split(":")[3])
    coupon_service = CouponService(session)
    coupon = await coupon_service.coupon_repo.get_by_id(coupon_id)
    if not coupon:
        await callback.answer("Coupon not found", show_alert=True)
        return
    type_label = "%" if coupon.type.value == "percentage" else "Toman"
    text = (
        f"🎟 Coupon `{coupon.code}`\n\n"
        f"Type: {coupon.type.value}\n"
        f"Value: {coupon.value}{type_label}\n"
        f"Max discount: {coupon.max_discount or 'None'}\n"
        f"Min order: {coupon.min_order_amount or 'None'}\n"
        f"Used: {coupon.usage_count}\n"
        f"Active: {'🟢 yes' if coupon.is_active else '🔴 no'}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Toggle Active", callback_data=f"admin:coupon:toggle:{coupon.id}")
    kb.button(text="🗑 Delete", callback_data=f"admin:coupon:delete:{coupon.id}")
    kb.button(text="⬅️ Back", callback_data="admin:coupons")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:coupon:toggle:"))
async def admin_coupon_toggle(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    coupon_id = int(callback.data.split(":")[3])
    coupon_service = CouponService(session)
    coupon = await coupon_service.coupon_repo.get_by_id(coupon_id)
    if not coupon:
        await callback.answer("Coupon not found", show_alert=True)
        return
    await coupon_service.coupon_repo.update(coupon_id, {"is_active": not coupon.is_active})
    await callback.answer("Toggled")
    callback.data = f"admin:coupon:view:{coupon_id}"
    await admin_coupon_view(callback, session, lang)


@router.callback_query(F.data.startswith("admin:coupon:delete:"))
async def admin_coupon_delete(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    coupon_id = int(callback.data.split(":")[3])
    coupon_service = CouponService(session)
    coupon = await coupon_service.coupon_repo.get_by_id(coupon_id)
    if not coupon:
        await callback.answer("Coupon not found", show_alert=True)
        return
    await coupon_service.coupon_repo.delete(coupon_id)
    await callback.answer("Deleted")
    await admin_coupons_menu(callback, session, lang)


@router.callback_query(F.data == "admin:coupon:close")
async def admin_coupon_close(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await callback.answer()