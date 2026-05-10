from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.admin.dependencies import get_current_admin, get_current_admin_api
from app.core.database import db

router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def list_inventory(
    request: Request,
    business_id: Optional[int] = None,
    username: str = Depends(get_current_admin)
):
    """Cross-business inventory view."""
    query = {}
    if business_id:
        query["business_id"] = business_id
        
    items = await db.inventory.find(query).limit(200).to_list(200)
    
    # Let's get businesses map to display names easily
    b_docs = await db.businesses.find({}, {"telegram_user_id": 1, "business_name": 1}).to_list(None)
    b_map = {b["telegram_user_id"]: b.get("business_name", "Unknown") for b in b_docs}
    
    for item in items:
        item["business_name"] = b_map.get(item["business_id"], "Unknown")
    
    return templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "username": username,
            "items": items,
            "business_id": business_id
        }
    )

@router.post("/{item_id}/update")
async def update_inventory_item(
    item_id: str, # Assuming string ID representation, or we can use item name + business_id
    business_id: int = Form(...),
    name_normalized: str = Form(...),
    quantity: float = Form(...),
    low_stock_threshold: float = Form(...),
    username: str = Depends(get_current_admin_api)
):
    """Inline edit quantities/thresholds."""
    result = await db.inventory.update_one(
        {"business_id": business_id, "name_normalized": name_normalized},
        {"$set": {
            "quantity": quantity,
            "low_stock_threshold": low_stock_threshold,
            "last_deduction_source": "admin"
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
        
    return {"status": "success"}
