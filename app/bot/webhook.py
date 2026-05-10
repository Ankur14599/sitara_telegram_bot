"""
Webhook route — receives Telegram updates via POST /webhook/{token}.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.bot.application import get_application
from telegram import Update

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    """
    Receive incoming Telegram updates.
    Token in URL must match WEBHOOK_SECRET to prevent unauthorized access.
    """
    if token != settings.WEBHOOK_SECRET:
        logger.warning(f"Unauthorized webhook attempt with token: {token[:8]}...")
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    try:
        application = get_application()
        data = await request.json()
        update = Update.de_json(data, application.bot)

        # Process update asynchronously within PTB's framework
        await application.process_update(update)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}", exc_info=True)
        # Return 200 to prevent Telegram from retrying endlessly
        return {"ok": False, "error": str(e)}
