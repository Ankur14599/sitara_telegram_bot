import logging
from telegram import Bot
from telegram.error import TelegramError

from app.core.config import settings
from app.bot.application import get_application

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    async def send_message(chat_id: int, text: str, parse_mode: str = "Markdown", reply_markup=None) -> bool:
        """Send a message to a Telegram user."""
        try:
            app = get_application()
            await app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message to {chat_id}: {e}")
            return False

    @staticmethod
    async def send_document(chat_id: int, document: bytes, filename: str, caption: str = "") -> bool:
        """Send a document/file to a Telegram user."""
        try:
            app = get_application()
            await app.bot.send_document(
                chat_id=chat_id,
                document=document,
                filename=filename,
                caption=caption
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send document to {chat_id}: {e}")
            return False
