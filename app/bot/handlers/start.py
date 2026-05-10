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
✨ *Sitara — The Extensive Command Guide* ✨

I'm here to help you manage every aspect of your small business. Here is the full breakdown of how to use me:

*📦 ORDER MANAGEMENT*
• /neworder — Start a step-by-step wizard to create an order.
• /orders — List all active orders. Click the buttons to change status.
• /order `<number>` — Detailed view of a specific order (e.g., `/order 001`).
• /completeorder — Quick-select list to mark orders as finished.
• /cancelorder — Quick-select list to cancel an order.
• /invoice `<number>` — Generates a professional PDF invoice for that order.

*📊 INVENTORY & STOCK*
• /inventory — See everything you have in stock and what's running low.
• /addstock `<item> <qty>` — Add items (e.g., `/addstock flour 10kg`).
• /removestock `<item> <qty>` — Manually remove stock (e.g., `/removestock eggs 12`).
• /lowstock — View only the items that have dropped below your alert level.
• /setprice `<item> <price>` — Set the selling price for an inventory item.
• /setthreshold `<item> <qty>` — Set when you want a "Low Stock" warning.

*🧾 RECIPES (Bill of Materials)*
• /setbom `<product>` — Define a recipe (e.g., `/setbom cookie`). I'll ask what materials it uses.
• /bom `<product>` — View the recipe for a product.
• /boms — List all products that have recipes defined.
_Note: Inventory is auto-deducted when an order for these products is completed!_

*💰 PAYMENTS & REVENUE*
• /recordpayment `<order> <amount>` — Log a payment (e.g., `/recordpayment 001 500 upi`).
• /unpaid — See a list of all orders that haven't been fully paid yet.
• /revenue — Get a quick summary of money collected today, this week, and this month.

*📋 BUSINESS INSIGHTS*
• /summary — A snapshot of today's orders, payments, and stock alerts.
• /weeklysummary — A broader look at your performance over the last 7 days.
• /trends — See your best-selling items and top customers.

*⚙️ SYSTEM & HELP*
• /help — Show this guide.
• /start — Restart the bot or register your business.
• /cancel — Cancel any active wizard or conversation.

*💡 PRO TIP:* You don't always need commands!
Just tell me what's happening like you're talking to an assistant:
• _"order for Priya for 5 cupcakes for tomorrow 2pm"_
• _"i just used 2kg of sugar"_
• _"how many orders are pending?"_
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
