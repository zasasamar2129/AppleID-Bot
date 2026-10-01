import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.models.inventory import Inventory
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
INV_STATUS_ICON = {
    "available": "🟢",
    "reserved": "🟡",
    "sold": "🔴",
    "disabled": "⚪",
}

# Human labels for the fulfillment fields the supplier format produces.
_FULFILLMENT_LABELS = {
    "date_of_birth": "📅 Date of Birth",
    "school": "🧍‍♂️ School",
    "pet": "🧍‍♂️ Pet",
    "job": "👨‍⚕️ Job",
    "parents_meet": "🌆 Parents Meet",
    "notes": "📝 Notes",
}

PAGE_SIZE = 10


@router.callback_query(F.data == "admin:inventory:list")
async def inventory_list(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    await _render_inventory_page(callback, session, page=0, lang=lang)


@router.callback_query(F.data.startswith("admin:inventory:list:"))
async def inventory_list_page(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    """Paginated inventory list. Callback format: admin:inventory:list:<page>."""
    page = int(callback.data.rsplit(":", 1)[1])
    await _render_inventory_page(callback, session, page=page, lang=lang)


async def _render_inventory_page(
    callback: CallbackQuery, session: AsyncSession, page: int = 0, lang: str = "fa"
):
    repo = InventoryRepository(session)
    offset = page * PAGE_SIZE
    items = await repo.get_all(limit=PAGE_SIZE, offset=offset)
    if not items:
        if page == 0:
            kb_empty = InlineKeyboardBuilder()
            kb_empty.button(
                text="⬅️ " + get_text("common.back", lang),
                callback_data="admin:inventory",
            )
            kb_empty.adjust(1)
            await callback.message.edit_text(
                get_text(
                    "admin.inventory.no_inventory", lang, default="No inventory found."
                ),
                reply_markup=kb_empty.as_markup(),
            )
        await callback.answer()
        return

    text = f"📋 Inventory (page {page + 1})\n\n"
    kb = InlineKeyboardBuilder()
    for inv in items:
        icon = INV_STATUS_ICON.get(inv.status.value, "•")
        product_name = inv.product.name if inv.product else f"#{inv.product_id}"
        text += f"{icon} #{inv.id} · {product_name} · {inv.status.value}\n"
        kb.button(
            text=f"#{inv.id} — {product_name}",
            callback_data=f"admin:inventory:view:{inv.id}",
        )
    kb.adjust(1)

    # Pagination row.
    if page > 0:
        kb.row(
            InlineKeyboardButton(text="⬅️", callback_data=f"admin:inventory:list:{page - 1}")
        )
        if len(items) == PAGE_SIZE:
            kb.row(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"admin:inventory:list:{page + 1}"
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(text="➡️", callback_data="noop"),
            )
    elif len(items) == PAGE_SIZE:
        kb.row(
            InlineKeyboardButton(text="➡️", callback_data=f"admin:inventory:list:{page + 1}")
        )

    kb.row(
        InlineKeyboardButton(text="➕ Add", callback_data="admin:inventory:add"),
        InlineKeyboardButton(text="📥 Bulk", callback_data="admin:inventory:bulk"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="admin:inventory"),
    )

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:inventory:view:"))
async def inventory_view_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    """Show one inventory item with decrypted account and fulfillment data."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    inv_id = int(callback.data.rsplit(":", 1)[1])
    # Load the inventory WITH its product so `inv.product` is available
    # without triggering a lazy load (which would fail on the event loop).
    stmt = select(Inventory).options(selectinload(Inventory.product)).where(Inventory.id == inv_id)
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if not inv:
        await callback.answer("Not found", show_alert=True)
        return

    inventory_service = InventoryService(session)
    account = await inventory_service.decrypt_inventory(inv)
    fulfillment = await inventory_service.get_fulfillment_data(inv)

    icon = INV_STATUS_ICON.get(inv.status.value, "•")
    product_name = inv.product.name if inv.product else f"#{inv.product_id}"

    text = f"{icon} Inventory #{inv.id}\n\n"
    text += f"Product: {product_name}\n"
    text += f"Status: {inv.status.value}\n"
    if inv.region:
        text += f"Region: {inv.region}\n"
    if inv.internal_notes:
        text += f"📝 Notes: {inv.internal_notes}\n"

    text += "\n── Account ──\n"
    if account:
        text += f"📧 {account.get('email', '—')}\n"
        text += f"🔑 {account.get('password', '—')}\n"
    else:
        text += "(could not decrypt)\n"

    if fulfillment:
        text += "\n── Fulfillment ──\n"
        for key, value in fulfillment.items():
            if value in (None, ""):
                continue
            label = _FULFILLMENT_LABELS.get(key, key.replace("_", " ").title())
            text += f"{label}: {value}\n"

    text += "\n── Timeline ──\n"
    text += f"Created: {inv.created_at:%Y-%m-%d %H:%M} UTC\n"
    if inv.reserved_at:
        text += f"Reserved: {inv.reserved_at:%Y-%m-%d %H:%M} UTC\n"
    if inv.reservation_expires_at:
        text += f"Expires: {inv.reservation_expires_at:%Y-%m-%d %H:%M} UTC\n"
    if inv.sold_at:
        text += f"Sold: {inv.sold_at:%Y-%m-%d %H:%M} UTC\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back to list", callback_data="admin:inventory:list:0")
    kb.button(text="🏠 Inventory menu", callback_data="admin:inventory")
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
            default=(
                "Send multiple Apple ID accounts. One per line, "
                "in this format:\n\n🍏 email\n🗝 password\n\n"
                "You may repeat the emoji lines for each account "
                "(one blank line between accounts)."
            )
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

    await message.answer(
        get_text(
            "admin.inventory.bulk_added",
            lang,
            count=added,
            default=f"✅ Added {added} Apple ID(s).",
        )
    )
    await state.clear()
