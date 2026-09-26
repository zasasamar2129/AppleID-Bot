from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import InventoryStatus, OrderStatus, PaymentStatus, SupportStatus
from app.database.models.inventory import Inventory
from app.database.models.order import Order
from app.database.models.payment import Payment
from app.database.models.support import SupportTicket
from app.database.models.user import User


class StatisticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_stats(self, period: str = "all") -> dict[str, Any]:
        # period: today, yesterday, 7days, 30days, all
        now = datetime.utcnow()
        start_date = None
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "7days":
            start_date = now - timedelta(days=7)
        elif period == "30days":
            start_date = now - timedelta(days=30)
        # else: all time

        stats = {}
        # Users
        user_query = select(func.count()).select_from(User)
        if start_date:
            user_query = user_query.where(User.created_at >= start_date)
        stats["total_users"] = (await self.session.execute(user_query)).scalar_one()

        # Orders
        order_query = select(func.count()).select_from(Order)
        if start_date:
            order_query = order_query.where(Order.created_at >= start_date)
        stats["total_orders"] = (await self.session.execute(order_query)).scalar_one()

        # Completed orders
        completed_query = select(func.count()).select_from(Order).where(Order.status == OrderStatus.DELIVERED)
        if start_date:
            completed_query = completed_query.where(Order.created_at >= start_date)
        stats["completed_orders"] = (await self.session.execute(completed_query)).scalar_one()

        # Pending orders
        pending_query = select(func.count()).select_from(Order).where(Order.status.in_([OrderStatus.PENDING_PAYMENT, OrderStatus.PAID, OrderStatus.PROCESSING]))
        if start_date:
            pending_query = pending_query.where(Order.created_at >= start_date)
        stats["pending_orders"] = (await self.session.execute(pending_query)).scalar_one()

        # Cancelled orders
        cancelled_query = select(func.count()).select_from(Order).where(Order.status == OrderStatus.CANCELLED)
        if start_date:
            cancelled_query = cancelled_query.where(Order.created_at >= start_date)
        stats["cancelled_orders"] = (await self.session.execute(cancelled_query)).scalar_one()

        # Revenue
        revenue_query = select(func.sum(Order.final_price)).select_from(Order).where(Order.status.in_([OrderStatus.DELIVERED, OrderStatus.FULFILLED]))
        if start_date:
            revenue_query = revenue_query.where(Order.created_at >= start_date)
        revenue = (await self.session.execute(revenue_query)).scalar_one() or Decimal("0")
        stats["revenue"] = revenue

        # Inventory
        avail_inv = select(func.count()).select_from(Inventory).where(Inventory.status == InventoryStatus.AVAILABLE)
        stats["available_inventory"] = (await self.session.execute(avail_inv)).scalar_one()
        res_inv = select(func.count()).select_from(Inventory).where(Inventory.status == InventoryStatus.RESERVED)
        stats["reserved_inventory"] = (await self.session.execute(res_inv)).scalar_one()
        sold_inv = select(func.count()).select_from(Inventory).where(Inventory.status == InventoryStatus.SOLD)
        stats["sold_inventory"] = (await self.session.execute(sold_inv)).scalar_one()

        # Pending payments
        pend_pay = select(func.count()).select_from(Payment).where(Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PENDING_VERIFICATION]))
        stats["pending_payments"] = (await self.session.execute(pend_pay)).scalar_one()

        # Open support tickets
        open_tickets = select(func.count()).select_from(SupportTicket).where(SupportTicket.status.in_([SupportStatus.OPEN, SupportStatus.IN_PROGRESS]))
        stats["open_tickets"] = (await self.session.execute(open_tickets)).scalar_one()

        return stats
