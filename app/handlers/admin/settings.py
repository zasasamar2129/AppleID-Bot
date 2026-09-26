from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.services.settings_service import SettingsService
from app.states.admin.settings import AdminSettingsStates

router = Router()
router.callback_query.filter(IsAdmin())

PAYMENT_METHOD_LABELS = {
    "payment_online_enabled": "🌐 Online",
    "payment_card_enabled": "💳 Card-to-Card",
    "payment_wallet_enabled": "💰 Wallet",
}


def _status_icon(enabled: bool) -> str:
    return "🟢 ON" if enabled else "🔴 OFF"


@router.callback_query(F.data == "admin:settings")
async def settings_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    settings_service = SettingsService(session)
    maintenance = await settings_service.get("maintenance_mode", False)
    default_lang = await settings_service.get("default_language", "fa")
    currency = await settings_service.get("default_currency", "IRR")
    card_number = await settings_service.get("card_to_card_number", "Not set")
    payment_methods = await settings_service.get_payment_methods()

    text = (
        f"⚙️ Settings\n\n"
        f"Maintenance: {'ON' if maintenance else 'OFF'}\n"
        f"Default Language: {default_lang}\n"
        f"Currency: {currency}\n"
        f"Card Number: {card_number}\n\n"
        f"🔒 Payment Methods:\n"
        + "\n".join(f"  {_status_icon(v)} {PAYMENT_METHOD_LABELS[k]}" for k, v in payment_methods.items())
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🛠 Maintenance Mode", callback_data="admin:settings:maintenance")
    kb.button(text="🌐 Default Language", callback_data="admin:settings:language")
    kb.button(text="💳 Card-to-Card", callback_data="admin:settings:card")
    kb.button(text="🔒 Payment Methods", callback_data="admin:settings:payments")
    kb.button(text="📝 Delivery Footer", callback_data="admin:settings:footer")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:settings:payments")
async def payments_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    settings_service = SettingsService(session)
    payment_methods = await settings_service.get_payment_methods()

    text = "🔒 Payment Methods\n\n" + "\n".join(
        f"  {_status_icon(v)} {PAYMENT_METHOD_LABELS[k]}" for k, v in payment_methods.items()
    )
    kb = InlineKeyboardBuilder()
    for key, label in PAYMENT_METHOD_LABELS.items():
        kb.button(text=f"Toggle {label}", callback_data=f"admin:settings:togglepay:{key}")
    kb.button(text="⬅️ Back", callback_data="admin:settings")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:settings:togglepay:"))
async def toggle_payment(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    key = callback.data.split(":", 3)[3]
    if key not in PAYMENT_METHOD_LABELS:
        await callback.answer("Invalid payment method", show_alert=True)
        return
    settings_service = SettingsService(session)
    payment_methods = await settings_service.get_payment_methods()
    current = payment_methods.get(key, True)
    await settings_service.set_payment_method(key, not current)
    # Refresh display
    await payments_menu(callback, session, lang)
    await callback.answer(f"{PAYMENT_METHOD_LABELS[key]} → {'ON' if not current else 'OFF'}")


@router.callback_query(F.data == "admin:settings:footer")
async def footer_menu(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text="🇮🇷 Persian Footer", callback_data="admin:footer:fa")
    kb.button(text="🇬🇧 English Footer", callback_data="admin:footer:en")
    kb.button(text="⬅️ Back", callback_data="admin:settings")
    kb.adjust(1)
    await callback.message.edit_text("📝 Delivery Footer", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:footer:"))
async def footer_view(callback: CallbackQuery, session: AsyncSession, state: FSMContext, lang="fa"):
    lang_code = callback.data.split(":")[2]
    if lang_code not in ["fa", "en"]:
        await callback.answer("Invalid language", show_alert=True)
        return
    settings_service = SettingsService(session)
    key = f"delivery_footer_{lang_code}"
    current = await settings_service.get(key, "")
    await state.update_data(footer_lang=lang_code)
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Edit", callback_data=f"admin:footer:edit:{lang_code}")
    kb.button(text="⬅️ Back", callback_data="admin:settings:footer")
    kb.adjust(1)
    text = f"Current {lang_code.upper()} Footer:\n\n{current}"
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:footer:edit:"))
async def footer_edit_prompt(callback: CallbackQuery, state: FSMContext, lang="fa"):
    lang_code = callback.data.split(":")[3]
    await state.update_data(footer_lang=lang_code)
    await callback.message.answer(f"Send the new {lang_code.upper()} footer text:")
    await state.set_state(AdminSettingsStates.EDIT_FOOTER)
    await callback.answer()


@router.message(AdminSettingsStates.EDIT_FOOTER)
async def footer_edit_save(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    lang_code = data.get("footer_lang")
    new_footer = message.text.strip()
    if not new_footer:
        await message.answer("Footer cannot be empty.")
        return
    settings_service = SettingsService(session)
    key = f"delivery_footer_{lang_code}"
    await settings_service.set(key, new_footer)
    await message.answer(f"✅ Footer updated for {lang_code}.")
    await state.clear()
