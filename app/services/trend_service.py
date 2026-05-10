"""
Trend analytics for dashboard and Telegram business questions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import get_db


class TrendService:
    """Aggregate order and customer trends for a single business."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    @staticmethod
    def since(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def top_items_pipeline(business_id: int, since: datetime, limit: int = 10) -> list[dict[str, Any]]:
        return [
            {"$match": {"business_id": business_id, "created_at": {"$gte": since}}},
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": {"$toLower": "$items.name"},
                    "item": {"$first": "$items.name"},
                    "quantity": {"$sum": {"$ifNull": ["$items.quantity", 1]}},
                    "orders": {"$sum": 1},
                    "revenue": {"$sum": {"$ifNull": ["$items.total_price", 0]}},
                }
            },
            {"$sort": {"quantity": -1, "orders": -1}},
            {"$limit": limit},
        ]

    @staticmethod
    def top_customers_pipeline(business_id: int, since: datetime, limit: int = 10) -> list[dict[str, Any]]:
        return [
            {"$match": {"business_id": business_id, "created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$toLower": "$customer_name"},
                    "customer": {"$first": "$customer_name"},
                    "orders": {"$sum": 1},
                    "revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                    "last_order": {"$max": "$created_at"},
                }
            },
            {"$sort": {"orders": -1, "revenue": -1}},
            {"$limit": limit},
        ]

    @staticmethod
    def status_pipeline(business_id: int, since: datetime) -> list[dict[str, Any]]:
        return [
            {"$match": {"business_id": business_id, "created_at": {"$gte": since}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

    @staticmethod
    def daily_orders_pipeline(business_id: int, since: datetime) -> list[dict[str, Any]]:
        return [
            {"$match": {"business_id": business_id, "created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "orders": {"$sum": 1},
                    "revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                }
            },
            {"$sort": {"_id": 1}},
        ]

    async def get_trends(self, days: int = 30, limit: int = 10) -> dict[str, Any]:
        since = self.since(days)
        db = get_db()

        top_items = await db.orders.aggregate(
            self.top_items_pipeline(self.business_id, since, limit)
        ).to_list(limit)
        top_customers = await db.orders.aggregate(
            self.top_customers_pipeline(self.business_id, since, limit)
        ).to_list(limit)
        statuses = await db.orders.aggregate(
            self.status_pipeline(self.business_id, since)
        ).to_list(20)
        daily_orders = await db.orders.aggregate(
            self.daily_orders_pipeline(self.business_id, since)
        ).to_list(days + 1)
        total_orders = await db.orders.count_documents(
            {"business_id": self.business_id, "created_at": {"$gte": since}}
        )

        return {
            "days": days,
            "top_items": top_items,
            "top_customers": top_customers,
            "statuses": statuses,
            "daily_orders": daily_orders,
            "total_orders": total_orders,
        }

    @staticmethod
    def format_trends(trends: dict[str, Any]) -> str:
        days = trends["days"]
        total_orders = trends["total_orders"]
        top_items = trends["top_items"]
        top_customers = trends["top_customers"]
        statuses = trends["statuses"]

        if total_orders == 0:
            return f"No orders found in the last {days} days yet."

        item_lines = []
        for idx, item in enumerate(top_items[:5], start=1):
            item_lines.append(
                f"{idx}. {item.get('item', 'Unknown')} - "
                f"{item.get('quantity', 0):g} units across {item.get('orders', 0)} order lines"
            )

        customer_lines = []
        for idx, customer in enumerate(top_customers[:5], start=1):
            customer_lines.append(
                f"{idx}. {customer.get('customer', 'Unknown')} - "
                f"{customer.get('orders', 0)} orders"
            )

        status_lines = [
            f"{status.get('_id', 'unknown').replace('_', ' ').title()}: {status.get('count', 0)}"
            for status in statuses
        ]

        return (
            f"*Trends for the last {days} days*\n\n"
            f"*Total orders:* {total_orders}\n\n"
            f"*Most ordered items:*\n{chr(10).join(item_lines) if item_lines else 'No item data yet.'}\n\n"
            f"*Top customers:*\n{chr(10).join(customer_lines) if customer_lines else 'No customer data yet.'}\n\n"
            f"*Order status mix:*\n{', '.join(status_lines) if status_lines else 'No status data yet.'}"
        )
