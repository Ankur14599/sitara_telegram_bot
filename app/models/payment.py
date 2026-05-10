"""
Payment model for tracking order payments.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PaymentMethod(str, Enum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    OTHER = "other"


class Payment(BaseModel):
    """Payment document schema."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    order_id: str = Field(..., description="Reference to orders collection _id")
    order_number: Optional[str] = None

    amount: float = Field(..., gt=0)
    method: PaymentMethod = Field(default=PaymentMethod.CASH)

    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}
