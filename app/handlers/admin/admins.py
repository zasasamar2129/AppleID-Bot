from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.enums import AdminRole
from app.database.repositories.admin_repo import AdminRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.states.admin.admin import AdminAdminStates

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


@router.callback_query(F.data == "admin:admins")
async def admins_list(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    admin_repo = AdminRepository(session)
    admins = await admin_repo.get_all()
    if not admins:
        await callback.message.edit_text("No admins found.")
        await callback.answer()
        return

    text = "👮 Administrators\n\n"
    for admin in admins:
        text += f"{admin.first_name} {admin.last_name or ''}\n"
        text += f"Telegram ID: {admin.telegram_id}\n"
        text += f"Role: {admin.role.value}\n"
        text += f"Active: {'Yes' if admin.is_active else 'No'}\n\n"

    kb = InlineKeyboardBuilder()
    for admin in admins:
        kb.button(text=f"Manage {admin.first_name}", callback_data=f"admin:manage_admin:{admin.id}")
    kb.button(text="➕ Add Admin", callback_data="admin:add_admin")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await callback.message.answer(get_text("admin.admins.prompt_id", lang))
    await state.set_state(AdminAdminStates.ADD_TELEGRAM_ID)
    await callback.answer()


@router.message(AdminAdminStates.ADD_TELEGRAM_ID)
async def add_admin_telegram_id(message: Message, state: FSMContext, lang="fa"):
    telegram_id_str = message.text.strip()
    if not telegram_id_str.isdigit():
        await message.answer(get_text("admin.admins.invalid_id", lang))
        return
    telegram_id = int(telegram_id_str)
    await state.update_data(telegram_id=telegram_id)

    kb = InlineKeyboardBuilder()
    for role in AdminRole:
        kb.button(text=role.value, callback_data=f"admin:role:{role.value}")
    kb.adjust(1)
    await message.answer(get_text("admin.admins.select_role", lang), reply_markup=kb.as_markup())
    await state.set_state(AdminAdminStates.SELECT_ROLE)


@router.callback_query(AdminAdminStates.SELECT_ROLE, F.data.startswith("admin:role:"))
async def add_admin_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    role_value = callback.data.split(":")[2]
    role = AdminRole(role_value)
    data = await state.get_data()
    telegram_id = data.get("telegram_id")

    admin_repo = AdminRepository(session)
    existing = await admin_repo.get_by_telegram_id(telegram_id)
    if existing:
        await callback.answer(get_text("admin.admins.exists", lang), show_alert=True)
        await state.clear()
        return

    admin = await admin_repo.create(
        telegram_id=telegram_id,
        first_name="Admin",
        role=role,
    )

    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="add_admin", target_type="admin", target_id=str(admin.id), metadata={"role": role.value})

    await callback.message.answer(get_text("admin.admins.added", lang, telegram_id=telegram_id, role=role.value))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("admin:manage_admin:"))
async def manage_admin(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    admin_id = int(callback.data.split(":")[2])
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by_id(admin_id)
    if not admin:
        await callback.answer("Admin not found", show_alert=True)
        return

    text = (
        f"👮 Admin Details\n\n"
        f"Name: {admin.first_name} {admin.last_name or ''}\n"
        f"Telegram ID: {admin.telegram_id}\n"
        f"Role: {admin.role.value}\n"
        f"Active: {'Yes' if admin.is_active else 'No'}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Change Role", callback_data=f"admin:change_role:{admin.id}")
    kb.button(text="🚫 Deactivate", callback_data=f"admin:deactivate:{admin.id}")
    kb.button(text="⬅️ Back", callback_data="admin:admins")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:change_role:"))
async def change_role(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    admin_id = int(callback.data.split(":")[2])
    kb = InlineKeyboardBuilder()
    for role in AdminRole:
        kb.button(text=role.value, callback_data=f"admin:set_role:{admin_id}:{role.value}")
    kb.button(text="⬅️ Back", callback_data=f"admin:manage_admin:{admin_id}")
    kb.adjust(1)
    await callback.message.edit_text(get_text("admin.admins.select_role", lang), reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set_role:"))
async def set_role(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    parts = callback.data.split(":")
    admin_id = int(parts[2])
    role_value = parts[3]
    role = AdminRole(role_value)
    admin_repo = AdminRepository(session)
    await admin_repo.update_role(admin_id, role)

    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="change_admin_role", target_type="admin", target_id=str(admin_id), metadata={"role": role.value})

    await callback.message.edit_text(f"✅ Role updated to {role.value}.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:deactivate:"))
async def deactivate_admin(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    admin_id = int(callback.data.split(":")[2])
    admin_repo = AdminRepository(session)
    await admin_repo.set_active(admin_id, False)

    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="deactivate_admin", target_type="admin", target_id=str(admin_id))

    await callback.message.edit_text("✅ Admin deactivated.")
    await callback.answer()
