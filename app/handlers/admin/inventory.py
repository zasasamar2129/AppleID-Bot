import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.product_repo import ProductRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.services.inventory_service import InventoryService
from app.states.admin.inventory import AdminInventoryStates

router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


@router.callback_query(F.data == "admin:inventory")
async def inventory_menu(callback: CallbackQuery, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Apple ID", callback_data="admin:inventory:add")
    kb.button(text="📥 Bulk Import", callback_data="admin:inventory:bulk")
    kb.button(text="📋 View Inventory", callback_data="admin:inventory:list")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(2)
    await callback.message.edit_text(get_text("admin.inventory", lang), reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:inventory:add")
async def add_inventory_select_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    product_repo = ProductRepository(session)
    products = await product_repo.get_all(include_inactive=False)
    if not products:
        await callback.answer(get_text("admin.inventory.no_products", lang), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.button(text=p.name, callback_data=f"admin:invprod:{p.id}")
    kb.button(text="⬅️ Back", callback_data="admin:inventory")
    kb.adjust(1)
    await callback.message.edit_text(get_text("admin.inventory.select_product", lang), reply_markup=kb.as_markup())
    await state.set_state(AdminInventoryStates.SELECT_PRODUCT)
    await callback.answer()


@router.callback_query(AdminInventoryStates.SELECT_PRODUCT, F.data.startswith("admin:invprod:"))
async def product_selected(callback: CallbackQuery, state: FSMContext, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(
        get_text("admin.inventory.format_prompt", lang)
    )
    await state.set_state(AdminInventoryStates.WAITING_FORMATTED_TEXT)
    await callback.answer()


@router.message(AdminInventoryStates.WAITING_FORMATTED_TEXT)
async def parse_formatted_text(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    text = message.text or ""
    email = re.search(r"🍏\s*(.+)", text)
    password = re.search(r"🗝\s*(.+)", text)
    dob = re.search(r"📅\s*(.+)", text)
    school = re.search(r"🧍‍♂️\s*School\s*:\s*(.+)", text, re.IGNORECASE)
    pet = re.search(r"🧍‍♂️\s*Pet\s*:\s*(.+)", text, re.IGNORECASE)
    job = re.search(r"👨‍⚕️\s*Job\s*:\s*(.+)", text, re.IGNORECASE)
    parents_meet = re.search(
        r"🌆\s*Parents\s*(?:Meet|meet)\s*:\s*(.+)", text, re.IGNORECASE
    )

    if not email or not password:
        await message.answer(get_text("admin.inventory.invalid_format", lang))
        return
    data = {
        "email": email.group(1).strip(),
        "password": password.group(1).strip(),
        "date_of_birth": dob.group(1).strip() if dob else "",
        "school": school.group(1).strip() if school else "",
        "pet": pet.group(1).strip() if pet else "",
        "job": job.group(1).strip() if job else "",
        "parents_meet": parents_meet.group(1).strip() if parents_meet else "",
    }
    masked_email = data["email"][:2] + "***" + data["email"].split("@")[-1] if "@" in data["email"] else data["email"]
    preview = f"🍏 Apple ID: {masked_email}\n🗝 Password: ********\n\n"
    if data["date_of_birth"]:
        preview += f"📅 DOB: {data['date_of_birth']}\n"
    if data["school"]:
        preview += f"🧍‍♂️ School: {data['school']}\n"
    if data["pet"]:
        preview += f"🧍‍♂️ Pet: {data['pet']}\n"
    if data["job"]:
        preview += f"👨‍⚕️ Job: {data['job']}\n"
    if data["parents_meet"]:
        preview += (
            f"🌆 Parents Meet: {data['parents_meet']}\n"
        )
    await state.update_data(inventory_data=data)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Save Apple ID", callback_data="admin:inventory:save")
    kb.button(text="❌ Cancel", callback_data="admin:inventory:cancel")
    kb.adjust(1)
    await message.answer(preview, reply_markup=kb.as_markup())


@router.callback_query(F.data == "admin:inventory:save")
async def save_inventory(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    inv_data = data.get("inventory_data")
    product_id = data.get("product_id")
    if not inv_data or not product_id:
        await callback.answer(get_text("admin.inventory.no_products", lang), show_alert=True)
        return
    inventory_service = InventoryService(session)
    inv = await inventory_service.add_inventory(
        product_id=product_id,
        account_data={"email": inv_data["email"], "password": inv_data["password"]},
        fulfillment_data={
            "date_of_birth": inv_data["date_of_birth"],
            "school": inv_data["school"],
            "pet": inv_data["pet"],
            "job": inv_data["job"],
            "parents_meet": inv_data["parents_meet"],
        },
        region=None,
        notes=None,
    )
    audit = AuditService(session)
    await audit.log(admin_telegram_id=callback.from_user.id, action="add_inventory", target_type="inventory", target_id=str(inv.id))
    await callback.message.edit_text(get_text("admin.inventory.added", lang, inv_id=inv.id))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin:inventory:cancel")
async def cancel_inventory(callback: CallbackQuery, state: FSMContext, lang="fa"):
    await state.clear()
    await callback.message.edit_text(get_text("admin.inventory.cancelled", lang))
    await callback.answer()


# ---------- View Inventory ----------
@router.callback_query(F.data == "admin:inventory:list")
async def inventory_list(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    repo = InventoryRepository(session)
    items = await repo.get_all(limit=50)
    if not items:
        await callback.message.edit_text(get_text("admin.inventory.no_inventory", lang, default="No inventory found."))
        await callback.answer()
        return

    text = "📋 " + get_text("admin.inventory", lang) + "\n\n"
    for inv in items:
        status = inv.status.value.upper()
        status_icon = "🟢" if inv.status.value == "available" else ("🟡" if inv.status.value == "reserved" else "🔴")
        product_name = inv.product.name if inv.product else f"#{inv.product_id}"
        text += f"{status_icon} {product_name} | {status} | #{inv.id}\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="admin:inventory")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ---------- Bulk Import ----------
@router.callback_query(F.data == "admin:inventory:bulk")
async def inventory_bulk_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    product_repo = ProductRepository(session)
    products = await product_repo.get_all(include_inactive=False)
    if not products:
        await callback.answer(get_text("admin.inventory.no_products", lang), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.button(text=p.name, callback_data=f"admin:invbulk_prod:{p.id}")
    kb.button(text="⬅️ " + get_text("common.back", lang), callback_data="admin:inventory")
    kb.adjust(1)
    await callback.message.edit_text(get_text("admin.inventory.bulk_select_product", lang, default="Select product:"), reply_markup=kb.as_markup())
    await state.set_state(AdminInventoryStates.SELECT_PRODUCT)
    await callback.answer()


@router.callback_query(AdminInventoryStates.SELECT_PRODUCT, F.data.startswith("admin:invbulk_prod:"))
async def inventory_bulk_select_product(callback: CallbackQuery, state: FSMContext, lang="fa"):
    product_id = int(callback.data.split(":")[2])
    await state.update_data(product_id=product_id, bulk_mode=True)
    await callback.message.edit_text(
        get_text(
            "admin.inventory.bulk_prompt",
            lang,
            default="Send multiple Apple ID accounts. One per line, in this format:\n\n🍏 email\n🗝 password\n\nYou may repeat the emoji lines for each account (one blank line between accounts)."
        )
    )
    await state.set_state(AdminInventoryStates.BULK_UPLOAD)
    await callback.answer()


@router.message(AdminInventoryStates.BULK_UPLOAD)
async def inventory_bulk_parse(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    text = message.text or ""
    data = await state.get_data()
    product_id = data.get("product_id")
    inventory_service = InventoryService(session)

    # Parse each account block: lines with 🍏 email and 🗝 password, plus the
    # optional fulfillment fields (📅 DOB, 🧍‍♂️School, 👨‍⚕️job, 🌆 parentsmeet).
    #
    # IMPORTANT: a NEW 🍏 email line starts the next account. Blank lines are
    # only visual separators — the fulfillment lines of one account may appear
    # after a blank line (email → password → blank → DOB/School/job/parents).
    lines = text.splitlines()
    accounts = []
    current = {}

    def flush():
        if current.get("email") and current.get("password"):
            accounts.append(current.copy())
        current.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue  # blank line = separator, not a new account
        m_email = re.search(r"🍏\s*(.+)", line)
        m_pass = re.search(r"🗝\s*(.+)", line)
        m_dob = re.search(r"📅\s*(.+)", line)
        m_school = re.search(r"School\s*:\s*(.+)", line, re.IGNORECASE)
        m_pet = re.search(r"Pet\s*:\s*(.+)", line, re.IGNORECASE)
        m_job = re.search(r"job\s*:\s*(.+)", line, re.IGNORECASE)
        m_parents = re.search(
            r"Parents\s*(?:Meet|meet)\s*:\s*(.+)", line, re.IGNORECASE
        )

        if m_email:
            # A new email starts a new account; save the previous one first.
            if current.get("email"):
                flush()
            current["email"] = m_email.group(1).strip()
        elif m_pass:
            current["password"] = m_pass.group(1).strip()
        elif m_dob:
            current["date_of_birth"] = m_dob.group(1).strip()
        elif m_school:
            current["school"] = m_school.group(1).strip()
        elif m_pet:
            current["pet"] = m_pet.group(1).strip()
        elif m_job:
            current["job"] = m_job.group(1).strip()
        elif m_parents:
            current["parents_meet"] = m_parents.group(1).strip()
    flush()

    if not accounts:
        await message.answer(get_text("admin.inventory.invalid_format", lang))
        return

    added = 0
    for acc in accounts:
        fulfillment_data = {}
        for key in ("date_of_birth", "school", "pet", "job", "parents_meet"):
            if acc.get(key):
                fulfillment_data[key] = acc[key]
        account_data = {"email": acc["email"], "password": acc["password"]}
        await inventory_service.add_inventory(
            product_id=product_id,
            account_data=account_data,
            fulfillment_data=fulfillment_data or None,
        )
        added += 1

    audit = AuditService(session)
    await audit.log(
        admin_telegram_id=message.from_user.id,
        action="bulk_add_inventory",
        target_type="inventory",
        target_id=str(product_id),
        metadata={"count": added},
    )

    await message.answer(get_text("admin.inventory.bulk_added", lang, count=added, default=f"✅ Added {added} Apple ID(s)."))
    await state.clear()
