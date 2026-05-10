"""
Customer service — find_or_create with name normalization, CRUD + history.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.database import customers_col, orders_col

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for customer CRUD operations, scoped to a business_id."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a customer name for matching (lowercase, stripped)."""
        return name.strip().lower()

    # ── Find or Create ────────────────────────────────────────────────

    async def find_or_create(self, name: str) -> dict:
        """
        Find an existing customer by normalized name, or create a new one.
        Returns the customer document.
        """
        name_normalized = self.normalize_name(name)

        # Try to find existing
        customer = await customers_col().find_one({
            "business_id": self.business_id,
            "name_normalized": name_normalized,
        })

        if customer:
            return customer

        # Create new customer
        customer_doc = {
            "business_id": self.business_id,
            "name": name.strip().title(),  # Title case for display
            "name_normalized": name_normalized,
            "total_orders": 0,
            "total_spent": 0.0,
            "last_order_date": None,
            "phone": None,
            "telegram_username": None,
            "notes": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await customers_col().insert_one(customer_doc)
        customer_doc["_id"] = result.inserted_id

        logger.info(
            f"New customer '{name.strip()}' created for business_id={self.business_id}"
        )
        return customer_doc

    # ── Read ──────────────────────────────────────────────────────────

    async def get_customer(self, name: str) -> Optional[dict]:
        """Get a customer by name (normalized)."""
        return await customers_col().find_one({
            "business_id": self.business_id,
            "name_normalized": self.normalize_name(name),
        })

    async def get_customer_by_id(self, customer_id: str) -> Optional[dict]:
        """Get a customer by MongoDB _id."""
        from bson import ObjectId
        return await customers_col().find_one({
            "business_id": self.business_id,
            "_id": ObjectId(customer_id),
        })

    async def get_all_customers(self) -> list:
        """Get all customers for this business, sorted by name."""
        return await customers_col().find({
            "business_id": self.business_id,
        }).sort("name", 1).to_list(500)

    async def get_top_customers(self, limit: int = 5) -> list:
        """Get top customers by total spending."""
        return await customers_col().find({
            "business_id": self.business_id,
        }).sort("total_spent", -1).limit(limit).to_list(limit)

    # ── Update stats ──────────────────────────────────────────────────

    async def increment_order_stats(
        self, name: str, order_amount: float = 0.0
    ) -> Optional[dict]:
        """
        Increment total_orders and total_spent when a new order is placed.
        Updates last_order_date to now.
        """
        name_normalized = self.normalize_name(name)

        return await customers_col().find_one_and_update(
            {
                "business_id": self.business_id,
                "name_normalized": name_normalized,
            },
            {
                "$inc": {
                    "total_orders": 1,
                    "total_spent": order_amount,
                },
                "$set": {
                    "last_order_date": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            return_document=True,
        )

    # ── Update fields ─────────────────────────────────────────────────

    async def update_customer(self, name: str, updates: dict) -> Optional[dict]:
        """Update arbitrary fields on a customer."""
        updates["updated_at"] = datetime.now(timezone.utc)

        return await customers_col().find_one_and_update(
            {
                "business_id": self.business_id,
                "name_normalized": self.normalize_name(name),
            },
            {"$set": updates},
            return_document=True,
        )

    # ── Order history ─────────────────────────────────────────────────

    async def get_order_history(self, customer_name: str, limit: int = 10) -> list:
        """Get recent orders for a specific customer."""
        return await orders_col().find({
            "business_id": self.business_id,
            "customer_name": {"$regex": f"^{customer_name}$", "$options": "i"},
        }).sort("created_at", -1).limit(limit).to_list(limit)
