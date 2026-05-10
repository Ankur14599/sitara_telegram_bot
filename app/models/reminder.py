"""
Reminder model for deadline notifications.
Uses a polling pattern — one scheduled job checks all pending reminders.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Reminder(BaseModel):
    """Reminder document schema."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    order_id: str = Field(..., description="Reference to orders collection _id")
    order_number: Optional[str] = None

    scheduled_at: datetime = Field(..., description="UTC time to fire the reminder")
    hours_before_deadline: int = Field(..., description="How many hours before deadline")

    sent: bool = Field(default=False)
    sent_at: Optional[datetime] = None
    failed: bool = Field(default=False)
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
