from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates

from app.admin.dependencies import get_current_admin
from app.core.config import settings
from app.bot.application import build_application
import httpx

router = APIRouter(prefix="/admin/system", tags=["admin-system"])
templates = Jinja2Templates(directory="app/admin/templates")

@router.get("")
async def system_status(
    request: Request,
    username: str = Depends(get_current_admin)
):
    """View system status."""
    return templates.TemplateResponse(
        "system.html",
        {
            "request": request,
            "username": username,
            "webhook_url": settings.full_webhook_url
        }
    )

@router.post("/webhook")
async def register_webhook(
    request: Request,
    username: str = Depends(get_current_admin)
):
    """Manually re-register webhook."""
    bot_app = build_application()
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data={"url": settings.full_webhook_url})
        
    return {"status": res.json()}
