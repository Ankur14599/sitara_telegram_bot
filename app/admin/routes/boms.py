from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.admin.dependencies import get_current_admin
from app.core.database import db

router = APIRouter(prefix="/admin/boms", tags=["admin-boms"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def list_boms(
    request: Request,
    business_id: Optional[int] = None,
    username: str = Depends(get_current_admin)
):
    """List all BOMs (Bill of Materials)."""
    query = {}
    if business_id:
        query["business_id"] = business_id
        
    boms = await db.product_bom.find(query).limit(100).to_list(100)
    
    b_docs = await db.businesses.find({}, {"telegram_user_id": 1, "business_name": 1}).to_list(None)
    b_map = {b["telegram_user_id"]: b.get("business_name", "Unknown") for b in b_docs}
    
    for bom in boms:
        bom["business_name"] = b_map.get(bom["business_id"], "Unknown")
        
    return templates.TemplateResponse(
        "boms.html",
        {
            "request": request,
            "username": username,
            "boms": boms,
            "business_id": business_id
        }
    )
