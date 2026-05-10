"""
ProductBOM — bill of materials per product/order-item type.
Generalized for any business: bakery, tailor, florist, etc.
"""

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class BOMaterial(BaseModel):
    """Single material consumed by one unit of a product."""
    inventory_item_name: str
    inventory_item_normalized: str
    quantity_per_unit: float = Field(gt=0)
    unit: str = Field(default="pieces")


class ProductBOM(BaseModel):
    """Bill of materials for a product."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    product_name_normalized: str = Field(
        ...,
        description="Normalized order item name, e.g. 'chocolate cake'",
    )

    materials: List[BOMaterial] = Field(default_factory=list)

    confirmed: bool = Field(
        default=False,
        description="False = still in learning mode",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
