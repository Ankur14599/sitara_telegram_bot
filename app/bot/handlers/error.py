"""
Global error handler for the Telegram bot.
Logs errors and notifies the user when something goes wrong.
"""

import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for all uncaught exceptions in bot handlers.
    Logs the full traceback and sends a user-friendly message.
    """
    logger.error(
        f"Exception while handling an update: {context.error}",
        exc_info=context.error,
    )

    # Log the full traceback
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    logger.error(f"Traceback:\n{tb_string}")

    # Notify the user if we have an update with a message
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Sorry, something went wrong processing your request.\n"
                "Please try again. If the problem persists, use /help to see available commands."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
