"""
Business model — tenant anchor.
Each Telegram user maps to one business.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class Business(BaseModel):
    """Business (tenant anchor) document schema."""

    telegram_user_id: int = Field(..., description="Telegram user ID — unique partition key")
    business_name: str = Field(..., min_length=1, max_length=200)
    owner_name: str = Field(..., min_length=1, max_length=200)
    timezone: str = Field(default="Asia/Kolkata", description="IANA timezone string")
    currency_symbol: str = Field(default="₹")

    low_stock_threshold: int = Field(default=5, ge=0, description="Default threshold for new inventory items")
    reminder_hours_before: List[int] = Field(
        default=[24, 2],
        description="Hours before deadline to send reminders",
    )
    daily_summary_time: str = Field(
        default="20:00",
        description="HH:MM for daily summary push",
    )

    total_orders_lifetime: int = Field(
        default=0,
        ge=0,
        description="Atomic counter for order number generation",
    )

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class BusinessCreate(BaseModel):
    """Schema for creating a new business via /start."""

    telegram_user_id: int
    business_name: str = Field(..., min_length=1, max_length=200)
    owner_name: str = Field(..., min_length=1, max_length=200)
    timezone: str = Field(default="Asia/Kolkata")
    currency_symbol: str = Field(default="₹")
