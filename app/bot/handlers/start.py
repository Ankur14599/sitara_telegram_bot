"""
/start and /help command handlers.
/start registers the business (tenant) if not already registered.
"""

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from app.core.database import businesses_col

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """
🌟 *Hi there! I'm Sitara, your SmallBiz Assistant!*

Think of me as your business partner who's always on — I handle the boring bits so you can focus on what you do best. Here's what I can do:

📦 *Orders* — Create and track orders through natural conversation
📊 *Inventory* — Track stock levels with auto-deduction
👥 *Customers* — Manage profiles and order history
💰 *Payments* — Record payments and track balances
📋 *Reports* — Daily/weekly summaries and PDF invoices

*Getting Started:*
1️⃣ Just say hi and chat with me naturally!
2️⃣ Create orders: _"order for Priya for 2 cakes by friday 8pm"_
3️⃣ Update stock: _"added 10kg flour"_

Type /help to see all commands, or just start talking — I'm a good listener 😊
"""

HELP_MESSAGE = """
📚 *Sitara — Command Reference*

*📦 Orders*
/neworder — Guided order creation wizard
/orders — View all active orders (paginated)
/order `<number>` — View specific order details
/completeorder — Mark an order as complete
/cancelorder — Cancel an order

*📊 Inventory*
/inventory — View all stock with quantities
/addstock — Add items to inventory
/removestock — Manually deduct items
/lowstock — Items at or below threshold
/setprice — Set selling price for an item
/setthreshold — Set low-stock alert threshold

*🧾 Bill of Materials*
/bom `<product>` — View materials for a product
/setbom `<product>` — Define materials for a product
/boms — List all products with defined BOMs

*👥 Customers*
/customers — View all customers
/customer `<name>` — Customer profile + history
/topcustomers — Top 5 customers by revenue

*💰 Payments*
/recordpayment — Record payment for an order
/unpaid — Orders with outstanding balance
/revenue — Revenue summary (today/week/month)

*📋 Reports*
/summary — Today's business summary
/weeklysummary — This week's summary
/invoice `<number>` — Generate PDF invoice

*⚙️ Settings*
/settings — View/edit business settings
/settimezone — Set your timezone
/setreminders — Configure reminder times

*💡 Tip:* You can also just type naturally!
_"order for Priya for 2 cakes for friday 8pm"_
_"added 5kg flour"_
_"how many orders today?"_
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    Registers the business if this is a new user, or welcomes back existing users.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    try:
        # Check if business already exists
        existing = await businesses_col().find_one({"telegram_user_id": user.id})

        if existing:
            await update.message.reply_text(
                f"👋 *Hey {existing['owner_name']}!* Great to see you again!\n\n"
                f"🏢 *{existing['business_name']}* — I'm all set and ready to help.\n\n"
                f"Just talk to me naturally, or type /help to see everything I can do!",
                parse_mode="Markdown",
            )
            return

        # New user — create business with defaults
        # For now, use basic info from Telegram profile
        # TODO: Phase 2 will add a proper onboarding ConversationHandler
        business_doc = {
            "telegram_user_id": user.id,
            "business_name": f"{user.first_name}'s Business",
            "owner_name": user.first_name or "Owner",
            "timezone": "Asia/Kolkata",
            "currency_symbol": "₹",
            "low_stock_threshold": 5,
            "reminder_hours_before": [24, 2],
            "daily_summary_time": "20:00",
            "total_orders_lifetime": 0,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        await businesses_col().insert_one(business_doc)

        logger.info(f"New business registered: user_id={user.id}, name={user.first_name}")

        await update.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error in /start handler: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, something went wrong during setup. Please try /start again."
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command — show full command reference."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")
