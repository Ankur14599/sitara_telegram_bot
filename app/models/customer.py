"""
Customer model with order history tracking.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Customer document schema."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    name: str = Field(..., min_length=1)
    name_normalized: str = Field(..., description="Lowercase name for matching")

    total_orders: int = Field(default=0, ge=0)
    total_spent: float = Field(default=0.0, ge=0)
    last_order_date: Optional[datetime] = None

    phone: Optional[str] = None
    telegram_username: Optional[str] = None
    notes: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
