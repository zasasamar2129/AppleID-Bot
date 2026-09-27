from __future__ import annotations

from aiogram import Dispatcher

from app.bot.middlewares.db import DatabaseMiddleware
from app.bot.middlewares.i18n import I18nMiddleware
from app.bot.middlewares.maintenance import MaintenanceMiddleware
from app.bot.middlewares.throttle import ThrottlingMiddleware
from app.bot.middlewares.user import UserMiddleware
from app.handlers.admin.price_inquiry import router as admin_price_inquiry_router
from app.handlers.price_inquiry import router as price_inquiry_router

# inside register_all_routers, after the other includes:

def register_all_routers(dp: Dispatcher) -> None:
    # Import and include routers
    from app.handlers import (
        channel,
        coupons,
        errors,
        language,
        menu,
        orders,
        payment,
        products,
        profile,
        referrals,
        start,
        support,
        tutorial,
        unlock,
        wallet,
    )
    from app.handlers.admin import admins as admin_admins
    from app.handlers.admin import audit as admin_audit
    from app.handlers.admin import broadcast as admin_broadcast
    from app.handlers.admin import coupons as admin_coupons
    from app.handlers.admin import dashboard
    from app.handlers.admin import inventory as admin_inventory
    from app.handlers.admin import orders as admin_orders
    from app.handlers.admin import payments as admin_payments
    from app.handlers.admin import products as admin_products
    from app.handlers.admin import referrals as admin_referrals
    from app.handlers.admin import scheduler_health as admin_scheduler_health
    from app.handlers.admin import settings as admin_settings
    from app.handlers.admin import statistics as admin_statistics
    from app.handlers.admin import support as admin_support
    from app.handlers.admin import unlock as admin_unlock
    from app.handlers.admin import users as admin_users
    from app.handlers.admin import wallet as admin_wallet

    # User routers
    dp.include_router(start.router)
    dp.include_router(channel.router)
    dp.include_router(menu.router)
    dp.include_router(profile.router)
    dp.include_router(products.router)
    dp.include_router(orders.router)          # handles purchases
    dp.include_router(payment.router)
    dp.include_router(wallet.router)
    dp.include_router(coupons.router)
    dp.include_router(referrals.router)
    dp.include_router(support.router)
    dp.include_router(language.router)
    dp.include_router(errors.router)
    dp.include_router(price_inquiry_router)
    dp.include_router(unlock.router)
    dp.include_router(tutorial.router)
    dp.include_router(admin_price_inquiry_router)

    # Admin routers
    dp.include_router(dashboard.router)
    dp.include_router(admin_users.router)
    dp.include_router(admin_products.router)
    dp.include_router(admin_inventory.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_payments.router)
    dp.include_router(admin_wallet.router)
    dp.include_router(admin_coupons.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_support.router)
    dp.include_router(admin_referrals.router)
    dp.include_router(admin_statistics.router)
    dp.include_router(admin_scheduler_health.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_admins.router)
    dp.include_router(admin_unlock.router)
    dp.include_router(admin_audit.router)


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(DatabaseMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(I18nMiddleware())
    # Membership guard: runs after lang/db_user are set, before throttling
    # and the admin bypass (admins are exempt in the middleware itself).
    from app.bot.middlewares.membership import ChannelMembershipMiddleware
    dp.update.outer_middleware(ChannelMembershipMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware())
    dp.update.outer_middleware(MaintenanceMiddleware())
