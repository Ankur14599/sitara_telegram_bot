"""
Order model with status enum and line items.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class OrderItem(BaseModel):
    """Single line item within an order."""
    name: str
    quantity: float = Field(default=1, gt=0)
    unit_price: Optional[float] = Field(default=None, ge=0)
    total_price: Optional[float] = Field(default=None, ge=0)


class Order(BaseModel):
    """Order document schema."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    order_number: str = Field(..., description="e.g. ORD-2024-0001")
    customer_name: str
    customer_id: Optional[str] = Field(default=None, description="Reference to customers collection _id")

    items: List[OrderItem] = Field(default_factory=list)

    deadline: Optional[datetime] = Field(default=None, description="UTC deadline")
    deadline_raw: Optional[str] = Field(default=None, description="Original deadline string from user")

    status: OrderStatus = Field(default=OrderStatus.PENDING)

    subtotal: float = Field(default=0.0, ge=0)
    discount: float = Field(default=0.0, ge=0)
    total_amount: float = Field(default=0.0, ge=0)
    amount_paid: float = Field(default=0.0, ge=0)
    payment_status: PaymentStatus = Field(default=PaymentStatus.UNPAID)

    reminders_sent: List[datetime] = Field(default_factory=list)
    special_instructions: Optional[str] = None
    original_message: Optional[str] = Field(default=None, description="Raw NL text from user")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class OrderCreate(BaseModel):
    """Schema for NLP-extracted order data."""
    customer_name: str
    items: List[OrderItem]
    deadline: Optional[datetime] = None
    deadline_raw: Optional[str] = None
    deadline_confidence: Optional[str] = None
    special_instructions: Optional[str] = None
    is_valid_order: bool = True
    reason_if_invalid: Optional[str] = None
