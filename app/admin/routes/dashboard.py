from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone

from app.admin.dependencies import get_current_admin
from app.core.database import db

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    username: str = Depends(get_current_admin)
):
    """Admin dashboard with summary statistics."""
    # Gather stats
    total_businesses = await db.businesses.count_documents({})
    
    # Orders today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    orders_today = await db.orders.count_documents({
        "status": {"$in": ["completed", "ready", "in_progress", "pending"]},
        "deadline": {"$gte": today_start} # Approximating "created today" or "due today"
    })
    
    recent_activity = await db.activity_logs.find().sort("timestamp", -1).limit(10).to_list(10)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": username,
            "stats": {
                "total_businesses": total_businesses,
                "orders_today": orders_today,
            },
            "recent_activity": recent_activity
        }
    )
