from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.admin.dependencies import get_current_admin
from app.core.database import db

router = APIRouter(prefix="/admin/businesses", tags=["admin-businesses"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def list_businesses(
    request: Request,
    username: str = Depends(get_current_admin)
):
    """List all registered businesses."""
    businesses = await db.businesses.find().to_list(100)
    return templates.TemplateResponse(
        "businesses.html",
        {"request": request, "username": username, "businesses": businesses}
    )

@router.get("/{business_id}")
async def business_detail(
    request: Request,
    business_id: int,
    username: str = Depends(get_current_admin)
):
    """View details for a specific business."""
    business = await db.businesses.find_one({"telegram_user_id": business_id})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
        
    orders_count = await db.orders.count_documents({"business_id": business_id})
    inventory_count = await db.inventory.count_documents({"business_id": business_id})
    
    return templates.TemplateResponse(
        "business_detail.html",
        {
            "request": request,
            "username": username,
            "business": business,
            "stats": {
                "orders": orders_count,
                "inventory": inventory_count
            }
        }
    )
