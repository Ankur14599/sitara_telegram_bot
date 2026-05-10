"""
Inventory service — CRUD + fuzzy name matching, three-path deduction.
Handles: explicit text updates (Path 1), BOM auto-deduction (Path 2), admin edits (Path 3).
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId

from app.core.database import inventory_col, activity_logs_col
from app.models.inventory import DeductionSource

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for inventory operations, scoped to a business_id."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize an inventory item name for matching."""
        return name.strip().lower()

    # ── Add / Update stock ────────────────────────────────────────────

    async def add_stock(
        self,
        name: str,
        quantity: float,
        unit: Optional[str] = None,
        source: DeductionSource = DeductionSource.EXPLICIT,
    ) -> dict:
        """
        Add stock to an existing item, or create a new item if it doesn't exist.
        Returns the updated/created inventory doc.
        """
        name_normalized = self.normalize_name(name)
        now = datetime.now(timezone.utc)

        # Try to find existing item (exact normalized match first)
        existing = await self._find_item(name_normalized)

        if existing:
            old_qty = existing["quantity"]
            new_qty = old_qty + quantity

            update_fields = {
                "quantity": new_qty,
                "low_stock_alerted": False,  # Reset alert on restock
                "updated_at": now,
            }
            if unit:
                update_fields["unit"] = unit

            result = await inventory_col().find_one_and_update(
                {"_id": existing["_id"]},
                {"$set": update_fields},
                return_document=True,
            )

            await self._log_activity("add_stock", name, {
                "old_quantity": old_qty,
                "added": quantity,
                "new_quantity": new_qty,
                "unit": unit or existing.get("unit", "pieces"),
                "source": source.value,
            })

            logger.info(
                f"Stock added: {name} {old_qty} → {new_qty} "
                f"(business_id={self.business_id})"
            )
            return result
        else:
            # Create new inventory item
            return await self.create_item(name, quantity, unit or "pieces", source)

    async def create_item(
        self,
        name: str,
        quantity: float = 0.0,
        unit: str = "pieces",
        source: DeductionSource = DeductionSource.EXPLICIT,
        low_stock_threshold: Optional[float] = None,
    ) -> dict:
        """Create a new inventory item."""
        from app.core.database import businesses_col

        # Get default threshold from business config
        if low_stock_threshold is None:
            business = await businesses_col().find_one({
                "telegram_user_id": self.business_id
            })
            low_stock_threshold = float(business.get("low_stock_threshold", 5))

        now = datetime.now(timezone.utc)
        item_doc = {
            "business_id": self.business_id,
            "name": name.strip().title(),
            "name_normalized": self.normalize_name(name),
            "quantity": quantity,
            "unit": unit,
            "cost_price": None,
            "selling_price": None,
            "low_stock_threshold": low_stock_threshold,
            "low_stock_alerted": False,
            "last_deduction_source": source.value,
            "last_deduction_at": now,
            "created_at": now,
            "updated_at": now,
        }

        result = await inventory_col().insert_one(item_doc)
        item_doc["_id"] = result.inserted_id

        logger.info(
            f"New inventory item created: {name} ({quantity} {unit}) "
            f"for business_id={self.business_id}"
        )
        return item_doc

    # ── Deduct stock ──────────────────────────────────────────────────

    async def deduct_stock(
        self,
        name: str,
        quantity: float,
        source: DeductionSource = DeductionSource.EXPLICIT,
    ) -> Optional[dict]:
        """
        Deduct stock from an inventory item.
        Returns the updated doc, or None if item not found.
        Includes low-stock alert check.
        """
        name_normalized = self.normalize_name(name)
        existing = await self._find_item(name_normalized)

        if not existing:
            logger.warning(
                f"Deduct stock failed — item '{name}' not found "
                f"(business_id={self.business_id})"
            )
            return None

        old_qty = existing["quantity"]
        new_qty = max(0, old_qty - quantity)  # Don't go below 0
        now = datetime.now(timezone.utc)

        update_fields = {
            "quantity": new_qty,
            "last_deduction_source": source.value,
            "last_deduction_at": now,
            "updated_at": now,
        }

        result = await inventory_col().find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": update_fields},
            return_document=True,
        )

        await self._log_activity("deduct_stock", name, {
            "old_quantity": old_qty,
            "deducted": quantity,
            "new_quantity": new_qty,
            "source": source.value,
        })

        logger.info(
            f"Stock deducted: {name} {old_qty} → {new_qty} "
            f"(source={source.value}, business_id={self.business_id})"
        )

        return result

    async def set_stock(
        self,
        name: str,
        quantity: float,
        source: DeductionSource = DeductionSource.EXPLICIT,
    ) -> Optional[dict]:
        """Set stock to an exact quantity (e.g., 'I'm out of cocoa' → set to 0)."""
        name_normalized = self.normalize_name(name)
        existing = await self._find_item(name_normalized)

        if not existing:
            return None

        now = datetime.now(timezone.utc)
        return await inventory_col().find_one_and_update(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "quantity": quantity,
                    "last_deduction_source": source.value,
                    "last_deduction_at": now,
                    "updated_at": now,
                    "low_stock_alerted": False,
                },
            },
            return_document=True,
        )

    # ── Check low stock ───────────────────────────────────────────────

    async def check_low_stock(self, item: dict) -> bool:
        """
        Check if an item is below its low-stock threshold.
        Returns True if low-stock alert should be fired.
        """
        threshold = item.get("low_stock_threshold", 5.0)
        quantity = item.get("quantity", 0)
        already_alerted = item.get("low_stock_alerted", False)

        return quantity <= threshold and not already_alerted

    async def get_low_stock_items(self) -> list:
        """Get all items that are at or below their low-stock threshold."""
        # Use $expr to compare two fields within the document
        return await inventory_col().find({
            "business_id": self.business_id,
            "$expr": {"$lte": ["$quantity", "$low_stock_threshold"]},
        }).sort("quantity", 1).to_list(100)

    async def mark_low_stock_alerted(self, item_id: str) -> None:
        """Mark an item as having been alerted for low stock."""
        await inventory_col().update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {"low_stock_alerted": True}},
        )

    # ── Read ──────────────────────────────────────────────────────────

    async def get_all_items(self) -> list:
        """Get all inventory items for this business, sorted by name."""
        return await inventory_col().find({
            "business_id": self.business_id,
        }).sort("name", 1).to_list(500)

    async def get_item(self, name: str) -> Optional[dict]:
        """Get a single inventory item by name."""
        return await self._find_item(self.normalize_name(name))

    async def get_item_by_id(self, item_id: str) -> Optional[dict]:
        """Get a single inventory item by MongoDB _id."""
        return await inventory_col().find_one({
            "business_id": self.business_id,
            "_id": ObjectId(item_id),
        })

    # ── Update fields ─────────────────────────────────────────────────

    async def set_price(self, name: str, selling_price: float) -> Optional[dict]:
        """Set the selling price for an item."""
        item = await self._find_item(self.normalize_name(name))
        if not item:
            return None

        return await inventory_col().find_one_and_update(
            {"_id": item["_id"]},
            {
                "$set": {
                    "selling_price": selling_price,
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            return_document=True,
        )

    async def set_threshold(self, name: str, threshold: float) -> Optional[dict]:
        """Set the low-stock threshold for an item."""
        item = await self._find_item(self.normalize_name(name))
        if not item:
            return None

        return await inventory_col().find_one_and_update(
            {"_id": item["_id"]},
            {
                "$set": {
                    "low_stock_threshold": threshold,
                    "low_stock_alerted": False,  # Reset alert
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            return_document=True,
        )

    # ── Internal helpers ──────────────────────────────────────────────

    async def _find_item(self, name_normalized: str) -> Optional[dict]:
        """Find an inventory item by normalized name. Tries exact match first."""
        # Exact normalized match
        item = await inventory_col().find_one({
            "business_id": self.business_id,
            "name_normalized": name_normalized,
        })

        if item:
            return item

        # Fuzzy match — try partial substring match
        item = await inventory_col().find_one({
            "business_id": self.business_id,
            "name_normalized": {"$regex": f"^{name_normalized}$", "$options": "i"},
        })

        return item

    async def _log_activity(self, action: str, item_name: str, details: dict) -> None:
        """Log inventory activity for audit trail."""
        try:
            await activity_logs_col().insert_one({
                "business_id": self.business_id,
                "action": action,
                "entity_type": "inventory",
                "entity_id": item_name,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.error(f"Failed to log inventory activity: {e}")
