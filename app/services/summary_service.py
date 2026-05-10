from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.core.database import get_db
from app.models.order import OrderStatus

class SummaryService:
    def __init__(self, business_id: int):
        self.business_id = business_id

    async def get_daily_summary(self) -> str:
        """Generate a daily summary report."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        tomorrow_end = tomorrow_start + timedelta(days=1)

        # 1. Today's Revenue
        revenue_pipeline = [
            {
                "$match": {
                    "business_id": self.business_id,
                    "recorded_at": {"$gte": today_start, "$lt": tomorrow_start}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount"}
                }
            }
        ]
        rev_cursor = await get_db().payments.aggregate(revenue_pipeline).to_list(1)
        today_revenue = rev_cursor[0]["total"] if rev_cursor else 0.0

        # 2. Active Orders
        active_orders = await get_db().orders.count_documents({
            "business_id": self.business_id,
            "status": {"$in": [OrderStatus.PENDING.value, OrderStatus.IN_PROGRESS.value, OrderStatus.READY.value]}
        })

        # 3. Orders due tomorrow
        due_tomorrow = await get_db().orders.count_documents({
            "business_id": self.business_id,
            "status": {"$in": [OrderStatus.PENDING.value, OrderStatus.IN_PROGRESS.value, OrderStatus.READY.value]},
            "deadline": {"$gte": tomorrow_start, "$lt": tomorrow_end}
        })

        # 4. Low stock alerts
        low_stock = await get_db().inventory.count_documents({
            "business_id": self.business_id,
            "$expr": {"$lte": ["$quantity", "$low_stock_threshold"]}
        })

        text = (
            "📊 *Daily Summary*\n\n"
            f"• *Revenue Today:* ₹{today_revenue:.2f}\n"
            f"• *Active Orders:* {active_orders}\n"
            f"• *Orders Due Tomorrow:* {due_tomorrow}\n"
            f"• *Low Stock Items:* {low_stock}\n"
        )
        return text

    async def get_weekly_summary(self) -> str:
        """Generate a weekly summary report."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        # 1. Weekly Revenue
        revenue_pipeline = [
            {
                "$match": {
                    "business_id": self.business_id,
                    "recorded_at": {"$gte": week_start, "$lte": now}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount"}
                }
            }
        ]
        rev_cursor = await get_db().payments.aggregate(revenue_pipeline).to_list(1)
        weekly_revenue = rev_cursor[0]["total"] if rev_cursor else 0.0

        # 2. Orders completed this week
        completed_orders = await get_db().orders.count_documents({
            "business_id": self.business_id,
            "status": OrderStatus.COMPLETED.value,
            "updated_at": {"$gte": week_start, "$lte": now}
        })

        text = (
            "📊 *Weekly Summary*\n\n"
            f"• *Revenue This Week:* ₹{weekly_revenue:.2f}\n"
            f"• *Orders Completed:* {completed_orders}\n"
        )
        return text
