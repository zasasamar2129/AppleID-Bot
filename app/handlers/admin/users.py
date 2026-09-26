from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.localization import get_text
from app.security.audit import AuditService
from app.services.wallet_service import WalletService
from app.states.admin.user import AdminUserStates
from app.utils.formatting import format_price

router = Router()
router.callback_query.filter(IsAdmin())
router.message.filter(IsAdmin())


@router.callback_query(F.data == "admin:users")
async def users_list(callback: CallbackQuery, session: AsyncSession, page: int = 1, lang="fa"):
    user_repo = UserRepository(session)
    total_users = await user_repo.count()
    per_page = 10
    pages = max(1, (total_users + per_page - 1) // per_page)
    users = await user_repo.get_all(limit=per_page, offset=(page - 1) * per_page)
    if not users:
        await callback.message.edit_text("No users found.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for u in users:
        display_name = u.first_name + (f" {u.last_name}" if u.last_name else "")
        kb.button(text=f"{display_name} ({u.telegram_id})", callback_data=f"admin:user:{u.id}")
    if page > 1:
        kb.button(text="⬅️ Previous", callback_data=f"admin:users:page:{page-1}")
    kb.button(text=f"{page}/{pages}", callback_data="noop")
    if page < pages:
        kb.button(text="Next ➡️", callback_data=f"admin:users:page:{page+1}")
    kb.button(text="⬅️ Back", callback_data="admin:main")
    kb.adjust(1)
    await callback.message.edit_text("👥 Users", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users:page:"))
async def users_page(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    page = int(callback.data.split(":")[3])
    await users_list(callback, session, page, lang)


@router.callback_query(F.data.startswith("admin:user:"))
async def user_detail(callback: CallbackQuery, session: AsyncSession, lang="fa"):
    user_id = int(callback.data.split(":")[2])
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        await callback.answer("User not found", show_alert=True)
        return
    wallet_repo = WalletRepository(session)
    wallet = await wallet_repo.get_or_create(user.id)
    text = (
        f"👤 User Details\n\n"
        f"Name: {user.first_name} {user.last_name or ''}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Language: {user.language}\n"
        f"VIP: {'Yes' if user.is_vip else 'No'}\n"
        f"Blocked: {'Yes' if user.is_blocked else 'No'}\n"
        f"Wallet Balance: {format_price(wallet.balance, lang)}\n"
        f"Registered: {user.created_at.strftime('%Y-%m-%d')}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 Orders", callback_data=f"admin:user_orders:{user.id}")
    kb.button(text="💰 Adjust Wallet", callback_data=f"admin:adjust_wallet:{user.id}")
    kb.button(text="⬅️ Back", callback_data="admin:users")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# Wallet adjustment flow
@router.callback_query(F.data.startswith("admin:adjust_wallet:"))
async def adjust_wallet_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang="fa"):
    user_id = int(callback.data.split(":")[2])
    await state.update_data(user_id=user_id)
    await callback.message.answer(get_text("admin.users.prompt_adjust", lang))
    await state.set_state(AdminUserStates.WALLET_ADJUST_AMOUNT)
    await callback.answer()


@router.message(AdminUserStates.WALLET_ADJUST_AMOUNT)
async def wallet_adjust_amount(message: Message, state: FSMContext, lang="fa"):
    from decimal import Decimal, InvalidOperation
    try:
        amount = Decimal(message.text.strip())
    except (InvalidOperation, ValueError):
        await message.answer(get_text("admin.users.invalid_number", lang))
        return
    await state.update_data(amount=amount)
    await message.answer(get_text("admin.users.prompt_reason", lang))
    await state.set_state(AdminUserStates.WALLET_ADJUST_REASON)


@router.message(AdminUserStates.WALLET_ADJUST_REASON)
async def wallet_adjust_reason(message: Message, state: FSMContext, session: AsyncSession, lang="fa"):
    data = await state.get_data()
    user_id = data["user_id"]
    amount = data["amount"]
    reason = message.text.strip()

    wallet_service = WalletService(session)
    new_balance = await wallet_service.admin_adjust(user_id, amount, reason=reason, admin_id=message.from_user.id)

    audit = AuditService(session)
    await audit.log(
        admin_telegram_id=message.from_user.id,
        action="wallet_adjustment",
        target_type="user",
        target_id=str(user_id),
        metadata={"amount": str(amount), "reason": reason}
    )

    await message.answer(get_text("admin.users.adjusted", lang, balance=format_price(new_balance, lang)))
    await state.clear()
