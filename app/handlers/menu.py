from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.message_manager import MessageCleanupService

router = Router()


@router.callback_query(F.data == "menu:purchases")
async def menu_purchases(callback: CallbackQuery, session, db_user, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.orders import show_user_orders
    await show_user_orders(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(callback: CallbackQuery, session, db_user, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.profile import show_profile
    await show_profile(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:wallet")
async def menu_wallet(callback: CallbackQuery, session, db_user, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.wallet import show_wallet
    await show_wallet(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:coupon")
async def menu_coupon(callback: CallbackQuery, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.coupons import show_coupon_menu
    await show_coupon_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:referral")
async def menu_referral(callback: CallbackQuery, session, db_user, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.referrals import show_referral_info
    await show_referral_info(callback.message, session, db_user, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.support import show_support_menu
    await show_support_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:language")
async def menu_language(callback: CallbackQuery, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.language import show_language_menu
    await show_language_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "menu:about")
async def menu_about(callback: CallbackQuery, lang="fa"):
    # Delete current menu before navigation
    await MessageCleanupService.delete_message(callback.message.chat.id, callback.message.message_id)
    from app.handlers.about import show_about
    await show_about(callback.message, lang)
    await callback.answer()


# menu:unlock_apple_id is handled directly in unlock.py by unlock_entry()
