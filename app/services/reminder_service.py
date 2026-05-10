"""
Reminder service — schedule and cancel reminder documents.
Reminders are Reminder docs in MongoDB, polled by a 5-min scheduler job (Phase 3).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from bson import ObjectId

from app.core.database import reminders_col, businesses_col

logger = logging.getLogger(__name__)


class ReminderService:
    """Service for managing Reminder documents, scoped to a business_id."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    # ── Schedule reminders for an order ───────────────────────────────

    async def schedule_reminders(
        self,
        order_id: str,
        order_number: str,
        deadline: datetime,
    ) -> List[dict]:
        """
        Create Reminder documents based on the business's reminder_hours_before config.
        Default: [24, 2] → reminders at 24h and 2h before deadline.
        Returns list of created reminder docs.
        """
        # Get business config for reminder hours
        business = await businesses_col().find_one({
            "telegram_user_id": self.business_id,
        })
        if not business:
            logger.error(f"Business not found for user_id={self.business_id}")
            return []

        reminder_hours = business.get("reminder_hours_before", [24, 2])
        created_reminders = []
        now = datetime.now(timezone.utc)

        for hours in reminder_hours:
            scheduled_at = deadline - timedelta(hours=hours)

            # Skip if the scheduled time is already in the past
            if scheduled_at <= now:
                logger.debug(
                    f"Skipping reminder {hours}h before deadline — already past"
                )
                continue

            reminder_doc = {
                "business_id": self.business_id,
                "order_id": order_id,
                "order_number": order_number,
                "scheduled_at": scheduled_at,
                "hours_before_deadline": hours,
                "sent": False,
                "sent_at": None,
                "failed": False,
                "error_message": None,
                "created_at": now,
            }

            result = await reminders_col().insert_one(reminder_doc)
            reminder_doc["_id"] = result.inserted_id
            created_reminders.append(reminder_doc)

            logger.info(
                f"Reminder scheduled for {order_number}: {hours}h before deadline "
                f"(at {scheduled_at.isoformat()})"
            )

        return created_reminders

    # ── Cancel reminders ──────────────────────────────────────────────

    async def cancel_reminders_for_order(self, order_id: str) -> int:
        """
        Delete all unsent reminders for a specific order.
        Called when order is completed or cancelled.
        Returns count of deleted reminders.
        """
        result = await reminders_col().delete_many({
            "business_id": self.business_id,
            "order_id": order_id,
            "sent": False,
        })

        if result.deleted_count > 0:
            logger.info(
                f"Cancelled {result.deleted_count} unsent reminders for order_id={order_id}"
            )

        return result.deleted_count

    # ── Reschedule reminders ──────────────────────────────────────────

    async def reschedule_reminders(
        self,
        order_id: str,
        order_number: str,
        new_deadline: datetime,
    ) -> List[dict]:
        """
        Delete unsent reminders and create new ones for an updated deadline.
        Used when order deadline is changed.
        """
        await self.cancel_reminders_for_order(order_id)
        return await self.schedule_reminders(order_id, order_number, new_deadline)

    # ── Query ─────────────────────────────────────────────────────────

    async def get_pending_reminders(self, order_id: str) -> list:
        """Get all unsent reminders for an order."""
        return await reminders_col().find({
            "business_id": self.business_id,
            "order_id": order_id,
            "sent": False,
            "failed": False,
        }).sort("scheduled_at", 1).to_list(10)

    async def get_due_reminders(self) -> list:
        """
        Get all reminders that are due to be sent (for the scheduler job).
        Looks for unsent, unfailed reminders with scheduled_at <= now.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=10)  # catch near-misses

        return await reminders_col().find({
            "business_id": self.business_id,
            "sent": False,
            "failed": False,
            "scheduled_at": {"$lte": now, "$gte": window_start},
        }).to_list(100)

    async def mark_sent(self, reminder_id: str) -> None:
        """Mark a reminder as successfully sent."""
        await reminders_col().update_one(
            {"_id": ObjectId(reminder_id)},
            {
                "$set": {
                    "sent": True,
                    "sent_at": datetime.now(timezone.utc),
                },
            },
        )

    async def mark_failed(self, reminder_id: str, error: str) -> None:
        """Mark a reminder as failed."""
        await reminders_col().update_one(
            {"_id": ObjectId(reminder_id)},
            {
                "$set": {
                    "failed": True,
                    "error_message": error,
                },
            },
        )
