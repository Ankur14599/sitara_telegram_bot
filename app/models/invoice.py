"""
Invoice model for PDF generation tracking.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Invoice(BaseModel):
    """Invoice document schema — tracks generated invoices."""

    business_id: int = Field(..., description="telegram_user_id of the business owner")
    order_id: str = Field(..., description="Reference to orders collection _id")
    order_number: str
    invoice_number: str

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_to_telegram: bool = Field(default=False)
    file_path: Optional[str] = None

    model_config = {"populate_by_name": True}
