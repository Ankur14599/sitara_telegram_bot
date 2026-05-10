"""
Build the python-telegram-bot Application instance.
Webhook mode — initialize() at startup, do NOT call start().
"""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.core.config import settings
from app.bot.handlers.start import start_handler, help_handler
from app.bot.handlers.error import error_handler
from app.bot.handlers.natural_language import natural_language_handler
from app.bot.handlers.orders import (
    orders_handler,
    order_detail_handler,
    neworder_conversation,
    completeorder_handler,
    cancelorder_handler,
    invoice_handler,
)
from app.bot.handlers.inventory import (
    inventory_handler,
    addstock_handler,
    removestock_handler,
    lowstock_handler,
    setprice_handler,
    setthreshold_handler,
)
from app.bot.handlers.bom import (
    boms_handler,
    bom_detail_handler,
    bom_conversation,
)
from app.bot.handlers.payments import (
    record_payment_handler,
    unpaid_orders_handler,
    revenue_summary_handler,
)
from app.bot.handlers.summary import (
    summary_handler,
    weeklysummary_handler,
)
from app.bot.handlers.admin import broadcast_handler
from app.bot.handlers.callbacks import callback_router

logger = logging.getLogger(__name__)

# Module-level reference
_application: Application | None = None


def build_application() -> Application:
    """Build and configure the PTB Application with all handlers."""
    global _application

    builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN)
    app = builder.build()

    # ── Register handlers (order matters for MessageHandler) ──────────
    from app.bot.middleware import rate_limit_handler
    app.add_handler(rate_limit_handler, group=-1)

    # Conversation Handlers
    app.add_handler(neworder_conversation)
    app.add_handler(bom_conversation)

    # Command handlers — Basic
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))

    # Command handlers — Orders
    app.add_handler(CommandHandler("orders", orders_handler))
    app.add_handler(CommandHandler("order", order_detail_handler))
    app.add_handler(CommandHandler("neworder", neworder_conversation)) # already added as conversation, but for fallback
    app.add_handler(CommandHandler("completeorder", completeorder_handler))
    app.add_handler(CommandHandler("cancelorder", cancelorder_handler))
    app.add_handler(CommandHandler("invoice", invoice_handler))

    # Command handlers — Inventory
    app.add_handler(CommandHandler("inventory", inventory_handler))
    app.add_handler(CommandHandler("addstock", addstock_handler))
    app.add_handler(CommandHandler("removestock", removestock_handler))
    app.add_handler(CommandHandler("lowstock", lowstock_handler))
    app.add_handler(CommandHandler("setprice", setprice_handler))
    app.add_handler(CommandHandler("setthreshold", setthreshold_handler))

    # Command handlers — BOM
    app.add_handler(CommandHandler("boms", boms_handler))
    app.add_handler(CommandHandler("bom", bom_detail_handler))

    # Command handlers — Payments
    app.add_handler(CommandHandler("recordpayment", record_payment_handler))
    app.add_handler(CommandHandler("unpaid", unpaid_orders_handler))
    app.add_handler(CommandHandler("revenue", revenue_summary_handler))

    # Command handlers — Summary
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("weeklysummary", weeklysummary_handler))
    
    # Command handlers — Admin
    app.add_handler(CommandHandler("broadcast", broadcast_handler))

    # Callback Query Handler (Inline keyboards)
    app.add_handler(CallbackQueryHandler(callback_router))

    # Natural Language Handler (Fallback for all non-command text messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_handler))

    # Error handler
    app.add_error_handler(error_handler)

    _application = app
    logger.info("Telegram bot application built with all handlers")
    return app


def get_application() -> Application:
    """Return the active PTB Application. Raises if not built."""
    if _application is None:
        raise RuntimeError("Bot application not built. Call build_application() first.")
    return _application
