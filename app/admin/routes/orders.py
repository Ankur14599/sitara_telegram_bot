from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.admin.dependencies import get_current_admin, get_current_admin_api
from app.core.database import db

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def list_orders(
    request: Request,
    business_id: Optional[int] = None,
    username: str = Depends(get_current_admin)
):
    """List all orders, optionally filtered by business."""
    query = {}
    if business_id:
        query["business_id"] = business_id
        
    orders = await db.orders.find(query).sort("deadline", -1).limit(100).to_list(100)
    
    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "username": username,
            "orders": orders,
            "business_id": business_id
        }
    )

@router.post("/{order_number}/status")
async def update_order_status(
    order_number: str,
    business_id: int = Form(...),
    status: str = Form(...),
    username: str = Depends(get_current_admin_api)
):
    """Update order status."""
    result = await db.orders.update_one(
        {"order_number": order_number, "business_id": business_id},
        {"$set": {"status": status}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return {"status": "success"}
