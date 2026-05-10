"""
Inventory item model with three-path deduction tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DeductionSource(str, Enum):
    EXPLICIT = "explicit"
    RECIPE = "recipe"
    ADMIN = "admin"
    BOM_AUTO = "bom_auto"


class InventoryItem(BaseModel):
    """Inventory item document schema."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    name: str = Field(..., min_length=1)
    name_normalized: str = Field(..., description="Lowercase name for matching")

    quantity: float = Field(default=0.0, ge=0)
    unit: str = Field(default="pieces")
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)

    low_stock_threshold: float = Field(default=5.0, ge=0)
    low_stock_alerted: bool = Field(
        default=False,
        description="Reset on restock to avoid alert spam",
    )

    last_deduction_source: Optional[DeductionSource] = None
    last_deduction_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class InventoryUpdate(BaseModel):
    """Schema for NLP-extracted inventory update."""
    item: str
    quantity: float = Field(gt=0)
    unit: Optional[str] = None
    direction: str = Field(description="'add' or 'remove'")
