"""
Order service — full CRUD + business logic.
Atomic order number generation, status transitions, BOM auto-deduction on completion.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId

from app.core.database import orders_col, businesses_col, activity_logs_col
from app.models.order import OrderStatus, PaymentStatus, OrderItem

logger = logging.getLogger(__name__)

# Number of orders per page in paginated views
ORDERS_PER_PAGE = 5


class OrderService:
    """Service for order CRUD operations, scoped to a business_id."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    # ── Order number generation (atomic) ──────────────────────────────

    async def _generate_order_number(self) -> str:
        """
        Generate the next order number using atomic $inc.
        Format: ORD-{year}-{number:04d}
        """
        result = await businesses_col().find_one_and_update(
            {"telegram_user_id": self.business_id},
            {"$inc": {"total_orders_lifetime": 1}},
            return_document=True,
        )
        if not result:
            raise ValueError(f"Business not found for user_id={self.business_id}")

        counter = result["total_orders_lifetime"]
        year = datetime.now(timezone.utc).year
        return f"ORD-{year}-{counter:04d}"

    # ── Create ────────────────────────────────────────────────────────

    async def create_order(
        self,
        customer_name: str,
        items: List[dict],
        deadline: Optional[datetime] = None,
        deadline_raw: Optional[str] = None,
        special_instructions: Optional[str] = None,
        original_message: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> dict:
        """
        Create a new order with auto-generated order number.
        Returns the inserted order document.
        """
        order_number = await self._generate_order_number()

        # Build order items
        order_items = []
        for item_data in items:
            order_items.append({
                "name": item_data.get("name", "Unknown"),
                "quantity": item_data.get("quantity", 1),
                "unit_price": item_data.get("unit_price"),
                "total_price": item_data.get("total_price"),
            })

        order_doc = {
            "business_id": self.business_id,
            "order_number": order_number,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "items": order_items,
            "deadline": deadline,
            "deadline_raw": deadline_raw,
            "status": OrderStatus.PENDING.value,
            "subtotal": 0.0,
            "discount": 0.0,
            "total_amount": 0.0,
            "amount_paid": 0.0,
            "payment_status": PaymentStatus.UNPAID.value,
            "reminders_sent": [],
            "special_instructions": special_instructions,
            "original_message": original_message,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await orders_col().insert_one(order_doc)
        order_doc["_id"] = result.inserted_id

        # Log activity
        await self._log_activity("create", "order", order_number, {
            "customer": customer_name,
            "items": [i["name"] for i in order_items],
        })

        logger.info(f"Order {order_number} created for business_id={self.business_id}")
        return order_doc

    # ── Read ──────────────────────────────────────────────────────────

    async def get_order(self, order_number: str) -> Optional[dict]:
        """Get a single order by order number, scoped to this business."""
        return await orders_col().find_one({
            "business_id": self.business_id,
            "order_number": order_number,
        })

    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        """Get a single order by MongoDB _id, scoped to this business."""
        return await orders_col().find_one({
            "business_id": self.business_id,
            "_id": ObjectId(order_id),
        })

    async def get_active_orders(self, page: int = 1) -> tuple[list, int]:
        """
        Get paginated active orders (not completed/cancelled).
        Returns (orders_list, total_count).
        """
        query = {
            "business_id": self.business_id,
            "status": {"$nin": [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]},
        }

        total = await orders_col().count_documents(query)
        skip = (page - 1) * ORDERS_PER_PAGE

        orders = await orders_col().find(query)\
            .sort("deadline", 1)\
            .skip(skip)\
            .limit(ORDERS_PER_PAGE)\
            .to_list(ORDERS_PER_PAGE)

        return orders, total

    async def get_orders_by_status(self, status: str) -> list:
        """Get all orders with a specific status."""
        return await orders_col().find({
            "business_id": self.business_id,
            "status": status,
        }).sort("deadline", 1).to_list(100)

    async def get_todays_orders(self) -> list:
        """Get orders created today."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return await orders_col().find({
            "business_id": self.business_id,
            "created_at": {"$gte": today_start},
        }).sort("created_at", -1).to_list(100)

    # ── Update status ─────────────────────────────────────────────────

    async def update_status(self, order_number: str, new_status: str) -> Optional[dict]:
        """Update order status. Returns updated doc or None if not found."""
        result = await orders_col().find_one_and_update(
            {
                "business_id": self.business_id,
                "order_number": order_number,
            },
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            return_document=True,
        )

        if result:
            await self._log_activity("update_status", "order", order_number, {
                "new_status": new_status,
            })

        return result

    async def complete_order(self, order_number: str) -> Optional[dict]:
        """
        Mark order as completed.
        Triggers BOM auto-deduction (Path 2) via bom_service.
        Returns the updated order doc.
        """
        order = await self.update_status(order_number, OrderStatus.COMPLETED.value)

        if order:
            # BOM auto-deduction on completion
            try:
                from app.services.bom_service import BOMService
                bom_svc = BOMService(self.business_id)
                deduction_report = await bom_svc.auto_deduct_for_order(order)
                if deduction_report:
                    order["_deduction_report"] = deduction_report
            except Exception as e:
                logger.error(f"BOM auto-deduction failed for {order_number}: {e}")
                order["_deduction_error"] = str(e)

            # Cancel unsent reminders
            try:
                from app.services.reminder_service import ReminderService
                reminder_svc = ReminderService(self.business_id)
                await reminder_svc.cancel_reminders_for_order(str(order["_id"]))
            except Exception as e:
                logger.error(f"Reminder cancellation failed for {order_number}: {e}")

        return order

    async def cancel_order(self, order_number: str) -> Optional[dict]:
        """Mark order as cancelled and clean up reminders."""
        order = await self.update_status(order_number, OrderStatus.CANCELLED.value)

        if order:
            # Cancel unsent reminders
            try:
                from app.services.reminder_service import ReminderService
                reminder_svc = ReminderService(self.business_id)
                await reminder_svc.cancel_reminders_for_order(str(order["_id"]))
            except Exception as e:
                logger.error(f"Reminder cancellation failed for {order_number}: {e}")

        return order

    # ── Update fields ─────────────────────────────────────────────────

    async def update_order(self, order_number: str, updates: dict) -> Optional[dict]:
        """Update arbitrary fields on an order."""
        updates["updated_at"] = datetime.now(timezone.utc)
        return await orders_col().find_one_and_update(
            {
                "business_id": self.business_id,
                "order_number": order_number,
            },
            {"$set": updates},
            return_document=True,
        )

    async def update_payment(
        self, order_number: str, amount_paid: float
    ) -> Optional[dict]:
        """Update the amount paid and payment status on an order."""
        order = await self.get_order(order_number)
        if not order:
            return None

        new_amount_paid = order.get("amount_paid", 0) + amount_paid
        total = order.get("total_amount", 0)

        if total > 0:
            if new_amount_paid >= total:
                payment_status = PaymentStatus.PAID.value
            elif new_amount_paid > 0:
                payment_status = PaymentStatus.PARTIAL.value
            else:
                payment_status = PaymentStatus.UNPAID.value
        else:
            payment_status = PaymentStatus.UNPAID.value

        return await self.update_order(order_number, {
            "amount_paid": new_amount_paid,
            "payment_status": payment_status,
        })

    # ── Activity logging ──────────────────────────────────────────────

    async def _log_activity(
        self, action: str, entity_type: str, entity_id: str, details: dict
    ) -> None:
        """Log an activity for audit trail."""
        try:
            await activity_logs_col().insert_one({
                "business_id": self.business_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
