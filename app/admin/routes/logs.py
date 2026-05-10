from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.admin.dependencies import get_current_admin
from app.core.database import db

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def list_logs(
    request: Request,
    business_id: Optional[int] = None,
    username: str = Depends(get_current_admin)
):
    """View activity logs."""
    query = {}
    if business_id:
        query["business_id"] = business_id
        
    logs = await db.activity_logs.find(query).sort("timestamp", -1).limit(200).to_list(200)
    
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "username": username,
            "logs": logs,
            "business_id": business_id
        }
    )
