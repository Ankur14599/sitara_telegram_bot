"""
BOM service — Bill of Materials CRUD, material deduction, check_bom() helper.
Handles: BOM creation, learning flow, auto-deduction on order completion.
Generalized for any business type (bakery, tailor, florist, etc.).
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from app.core.database import product_bom_col
from app.models.inventory import DeductionSource

logger = logging.getLogger(__name__)


class BOMService:
    """Service for BOM operations, scoped to a business_id."""

    def __init__(self, business_id: int):
        self.business_id = business_id

    @staticmethod
    def normalize_product_name(name: str) -> str:
        """Normalize product name for matching."""
        return name.strip().lower()

    # ── Check BOM ─────────────────────────────────────────────────────

    async def check_bom(self, product_name: str) -> Optional[dict]:
        """
        Check if a BOM exists for a product.
        Returns the BOM doc if found, None otherwise.
        Used during order creation to show deduction preview or trigger learning.
        """
        name_normalized = self.normalize_product_name(product_name)

        return await product_bom_col().find_one({
            "business_id": self.business_id,
            "product_name_normalized": name_normalized,
        })

    # ── Create / Update BOM ───────────────────────────────────────────

    async def create_or_update_bom(
        self,
        product_name: str,
        materials: List[dict],
        confirmed: bool = False,
    ) -> dict:
        """
        Create or update a BOM for a product.
        materials: list of {inventory_item_name, quantity_per_unit, unit}
        Returns the upserted BOM doc.
        """
        name_normalized = self.normalize_product_name(product_name)
        now = datetime.now(timezone.utc)

        # Normalize material entries
        normalized_materials = []
        for mat in materials:
            normalized_materials.append({
                "inventory_item_name": mat["inventory_item_name"].strip().title()
                    if "inventory_item_name" in mat
                    else mat.get("item", "").strip().title(),
                "inventory_item_normalized": (
                    mat.get("inventory_item_name", mat.get("item", ""))
                ).strip().lower(),
                "quantity_per_unit": float(mat.get("quantity_per_unit", mat.get("quantity", 0))),
                "unit": mat.get("unit", "pieces"),
            })

        bom_doc = {
            "business_id": self.business_id,
            "product_name_normalized": name_normalized,
            "materials": normalized_materials,
            "confirmed": confirmed,
            "updated_at": now,
        }

        result = await product_bom_col().update_one(
            {
                "business_id": self.business_id,
                "product_name_normalized": name_normalized,
            },
            {
                "$set": bom_doc,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        # Fetch and return the full doc
        full_doc = await self.check_bom(product_name)

        action = "updated" if result.matched_count > 0 else "created"
        logger.info(
            f"BOM {action} for '{product_name}' with {len(normalized_materials)} materials "
            f"(confirmed={confirmed}, business_id={self.business_id})"
        )

        return full_doc

    async def confirm_bom(self, product_name: str) -> Optional[dict]:
        """Confirm a BOM (mark as no longer in learning mode)."""
        name_normalized = self.normalize_product_name(product_name)

        return await product_bom_col().find_one_and_update(
            {
                "business_id": self.business_id,
                "product_name_normalized": name_normalized,
            },
            {
                "$set": {
                    "confirmed": True,
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            return_document=True,
        )

    # ── Get all BOMs ──────────────────────────────────────────────────

    async def get_all_boms(self) -> list:
        """Get all BOMs for this business."""
        return await product_bom_col().find({
            "business_id": self.business_id,
        }).sort("product_name_normalized", 1).to_list(100)

    # ── Delete BOM ────────────────────────────────────────────────────

    async def delete_bom(self, product_name: str) -> bool:
        """Delete a BOM for a product. Returns True if deleted."""
        name_normalized = self.normalize_product_name(product_name)
        result = await product_bom_col().delete_one({
            "business_id": self.business_id,
            "product_name_normalized": name_normalized,
        })
        return result.deleted_count > 0

    # ── Auto-deduction on order completion ────────────────────────────

    async def auto_deduct_for_order(self, order: dict) -> Optional[List[dict]]:
        """
        Auto-deduct inventory based on BOM when an order is completed.
        For each order item with a confirmed BOM, multiply materials by quantity
        and deduct from inventory.

        Returns a list of deduction reports, or None if no deductions made.
        """
        from app.services.inventory_service import InventoryService

        inv_svc = InventoryService(self.business_id)
        deduction_reports = []

        for item in order.get("items", []):
            item_name = item.get("name", "")
            item_qty = item.get("quantity", 1)

            bom = await self.check_bom(item_name)

            if not bom or not bom.get("confirmed"):
                continue

            item_report = {
                "product": item_name,
                "order_quantity": item_qty,
                "deductions": [],
            }

            for material in bom.get("materials", []):
                mat_name = material["inventory_item_name"]
                deduct_qty = material["quantity_per_unit"] * item_qty

                result = await inv_svc.deduct_stock(
                    mat_name, deduct_qty, source=DeductionSource.BOM_AUTO
                )

                deduction_entry = {
                    "material": mat_name,
                    "deducted": deduct_qty,
                    "unit": material.get("unit", "pieces"),
                }

                if result:
                    deduction_entry["new_quantity"] = result["quantity"]

                    # Check for low stock after deduction
                    if await inv_svc.check_low_stock(result):
                        deduction_entry["low_stock_alert"] = True
                        await inv_svc.mark_low_stock_alerted(str(result["_id"]))
                else:
                    deduction_entry["error"] = f"Item '{mat_name}' not found in inventory"

                item_report["deductions"].append(deduction_entry)

            deduction_reports.append(item_report)

        return deduction_reports if deduction_reports else None

    # ── Format BOM for display ────────────────────────────────────────

    @staticmethod
    def format_bom_display(bom: dict) -> str:
        """Format a BOM document for Telegram display."""
        product = bom.get("product_name_normalized", "Unknown").title()
        confirmed = "✅ Confirmed" if bom.get("confirmed") else "⏳ Pending Confirmation"
        materials = bom.get("materials", [])

        lines = [f"📦 *{product}* ({confirmed})"]
        lines.append("Materials per unit:")

        for mat in materials:
            name = mat.get("inventory_item_name", "?")
            qty = mat.get("quantity_per_unit", 0)
            unit = mat.get("unit", "pieces")
            lines.append(f"  • {qty}{unit} {name}")

        return "\n".join(lines)

    @staticmethod
    def format_deduction_report(reports: List[dict]) -> str:
        """Format deduction report for Telegram display after order completion."""
        lines = ["📊 *Inventory Deductions:*"]

        for report in reports:
            product = report["product"].title()
            qty = report["order_quantity"]
            lines.append(f"\n*{product}* (×{qty}):")

            for ded in report.get("deductions", []):
                mat = ded["material"]
                deducted = ded["deducted"]
                unit = ded.get("unit", "pieces")

                if "error" in ded:
                    lines.append(f"  ⚠️ {mat}: {ded['error']}")
                else:
                    new_qty = ded.get("new_quantity", "?")
                    alert = " ⚠️ LOW STOCK" if ded.get("low_stock_alert") else ""
                    lines.append(f"  • {mat}: -{deducted}{unit} → {new_qty}{unit}{alert}")

        return "\n".join(lines)
