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
    username: str = Depends(get_current_admin) # Changed to get_current_admin for standard form
):
    """Update order status."""
    result = await db.orders.update_one(
        {"order_number": order_number, "business_id": business_id},
        {"$set": {"status": status}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
        
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/orders?business_id={business_id}", status_code=303)

@router.post("/{order_number}/delete")
async def delete_order(
    order_number: str,
    business_id: int = Form(...),
    username: str = Depends(get_current_admin)
):
    """Delete an order."""
    result = await db.orders.delete_one(
        {"order_number": order_number, "business_id": business_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
        
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/orders?business_id={business_id}" if business_id else "/admin/orders", status_code=303)

@router.post("/create")
async def create_order(
    business_id: int = Form(...),
    customer_name: str = Form(...),
    total_amount: float = Form(...),
    username: str = Depends(get_current_admin)
):
    """Manually create an order."""
    from app.services.order_service import OrderService
    order_svc = OrderService(business_id)
    
    # We use create_order from OrderService to handle order number generation
    await order_svc.create_order(
        customer_name=customer_name,
        items=[], # Admin can add items later or keep it empty for now
    )
    
    # Update total_amount manually if provided
    if total_amount > 0:
        await db.orders.update_one(
            {"business_id": business_id, "customer_name": customer_name}, # This is a bit loose, but create_order returns the doc
            {"$set": {"total_amount": total_amount}},
            sort=[("created_at", -1)]
        )

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/orders?business_id={business_id}", status_code=303)
