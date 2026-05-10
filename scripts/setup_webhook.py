"""
Register the Telegram webhook with Telegram's API.
Run this script after deploying the bot.

Usage:
    python -m scripts.setup_webhook
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_webhook():
    """Register the webhook URL with Telegram."""
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    webhook_url = settings.full_webhook_url
    logger.info(f"Setting webhook to: {webhook_url}")

    try:
        # Delete any existing webhook first
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Existing webhook deleted")

        # Set the new webhook
        success = await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query", "edited_message"],
        )

        if success:
            logger.info(f"✅ Webhook set successfully: {webhook_url}")

            # Verify
            info = await bot.get_webhook_info()
            logger.info(f"Webhook info: url={info.url}, pending={info.pending_update_count}")
        else:
            logger.error("❌ Failed to set webhook")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        sys.exit(1)
    finally:
        await bot.close()


async def delete_webhook():
    """Remove the webhook (switch to polling mode)."""
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted successfully")
    finally:
        await bot.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        asyncio.run(delete_webhook())
    else:
        asyncio.run(setup_webhook())
