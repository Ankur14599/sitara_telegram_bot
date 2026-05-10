"""
Order command handlers — /orders, /neworder, /order, /completeorder, /cancelorder.
Paginated views and inline keyboard interactions.
"""

import logging
import math
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.core.database import businesses_col
from app.services.order_service import OrderService, ORDERS_PER_PAGE
from app.services.customer_service import CustomerService
from app.services.bom_service import BOMService
from app.bot.keyboards.order_keyboards import (
    order_actions_keyboard,
    orders_pagination_keyboard,
)

logger = logging.getLogger(__name__)

# Status display configuration
STATUS_EMOJI = {
    "pending": "🟡",
    "in_progress": "🔵",
    "ready": "🟢",
    "completed": "✅",
    "cancelled": "❌",
}

PAYMENT_EMOJI = {
    "unpaid": "🔴",
    "partial": "🟡",
    "paid": "🟢",
}


# ── /orders — paginated active orders ─────────────────────────────────


async def orders_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show paginated list of active orders."""
    user = update.effective_user
    page = 1

    # Check if page is specified as argument
    if context.args:
        try:
            page = max(1, int(context.args[0]))
        except ValueError:
            pass

    order_svc = OrderService(user.id)
    orders, total = await order_svc.get_active_orders(page)

    if not orders:
        await update.message.reply_text(
            "📦 No active orders found.\n\n"
            "Create one by typing naturally:\n"
            "_\"order for Priya for 2 cakes by friday 8pm\"_\n\n"
            "Or use /neworder for a guided wizard.",
            parse_mode="Markdown",
        )
        return

    total_pages = math.ceil(total / ORDERS_PER_PAGE)

    # Build order list message
    lines = [f"📦 *Active Orders* (Page {page}/{total_pages}, {total} total)\n"]

    for order in orders:
        status = order.get("status", "pending")
        emoji = STATUS_EMOJI.get(status, "⚪")
        pay_status = order.get("payment_status", "unpaid")
        pay_emoji = PAYMENT_EMOJI.get(pay_status, "⚪")

        order_num = order.get("order_number", "?")
        customer = order.get("customer_name", "?")

        items_summary = ", ".join(
            f"{i.get('quantity', 1)}× {i.get('name', '?')}"
            for i in order.get("items", [])
        )

        deadline_text = ""
        if order.get("deadline"):
            dl = order["deadline"]
            deadline_text = f"\n   📅 {dl.strftime('%d %b %I:%M %p')}"

        lines.append(
            f"{emoji} *{order_num}* — {customer}\n"
            f"   {items_summary}"
            f"{deadline_text}\n"
            f"   {pay_emoji} Payment: {pay_status.title()}"
        )

    message = "\n\n".join(lines)

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=orders_pagination_keyboard(page, total_pages),
    )


# ── /order <number> — view specific order ─────────────────────────────


async def order_detail_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """View details of a specific order."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Please specify an order number: `/order ORD-2024-0001`",
            parse_mode="Markdown",
        )
        return

    order_number = context.args[0].upper()
    if not order_number.startswith("ORD-"):
        order_number = f"ORD-{order_number}"

    order_svc = OrderService(user.id)
    order = await order_svc.get_order(order_number)

    if not order:
        await update.message.reply_text(f"❌ Order {order_number} not found.")
        return

    await _send_order_detail(update.message.reply_text, order)


# ── /neworder — guided wizard ─────────────────────────────────────────

# ConversationHandler states
CUSTOMER_NAME, ORDER_ITEMS, ORDER_DEADLINE = range(3)


async def neworder_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the guided order creation wizard."""
    await update.message.reply_text(
        "📝 *New Order Wizard*\n\n"
        "Step 1/3: What is the customer's name?",
        parse_mode="Markdown",
    )
    return CUSTOMER_NAME


async def neworder_customer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive customer name and ask for items."""
    context.user_data["new_order_customer"] = update.message.text.strip()

    await update.message.reply_text(
        "Step 2/3: What items should be in the order?\n\n"
        "Example: _2 chocolate cakes, 1 birthday cake_",
        parse_mode="Markdown",
    )
    return ORDER_ITEMS


async def neworder_items(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive items and ask for deadline."""
    context.user_data["new_order_items_text"] = update.message.text.strip()

    await update.message.reply_text(
        "Step 3/3: When is the deadline?\n\n"
        "Example: _Friday 8pm_ or _May 15 at 3pm_\n"
        "Type _skip_ to create without a deadline.",
        parse_mode="Markdown",
    )
    return ORDER_DEADLINE


async def neworder_deadline(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive deadline and create the order."""
    from app.services.groq_service import groq_service

    user = update.effective_user
    deadline_text = update.message.text.strip()

    customer_name = context.user_data.get("new_order_customer", "Unknown")
    items_text = context.user_data.get("new_order_items_text", "")

    # Get business timezone
    business = await businesses_col().find_one({"telegram_user_id": user.id})
    tz = business.get("timezone", "Asia/Kolkata") if business else "Asia/Kolkata"

    # Build a natural language message for extraction
    if deadline_text.lower() == "skip":
        nl_message = f"order for {customer_name} for {items_text}"
    else:
        nl_message = f"order for {customer_name} for {items_text} by {deadline_text}"

    # Use the NLP pipeline to extract structured data
    order_data = await groq_service.extract_order(nl_message, tz)

    if not order_data or not order_data.get("is_valid_order", False):
        await update.message.reply_text(
            "❌ Couldn't create the order. Please try again with /neworder."
        )
        # Clear user data
        context.user_data.pop("new_order_customer", None)
        context.user_data.pop("new_order_items_text", None)
        return ConversationHandler.END

    # Parse deadline
    deadline = None
    deadline_str = order_data.get("deadline")
    if deadline_str:
        try:
            from dateutil.parser import parse as dateparse
            deadline = dateparse(deadline_str)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Find or create customer
    customer_svc = CustomerService(user.id)
    customer = await customer_svc.find_or_create(customer_name)

    # Create order
    order_svc = OrderService(user.id)
    items = order_data.get("items", [{"name": items_text, "quantity": 1}])

    order = await order_svc.create_order(
        customer_name=customer["name"],
        items=items,
        deadline=deadline,
        deadline_raw=deadline_text if deadline_text.lower() != "skip" else None,
        original_message=nl_message,
        customer_id=str(customer["_id"]),
    )

    await customer_svc.increment_order_stats(customer_name)

    # Schedule reminders
    if deadline:
        reminder_svc = ReminderService(user.id)
        await reminder_svc.schedule_reminders(
            str(order["_id"]), order["order_number"], deadline
        )
        from app.services.reminder_service import ReminderService

    # Send confirmation
    items_display = "\n".join(
        f"  • {i.get('quantity', 1)}× {i.get('name', '?')}"
        for i in items
    )

    deadline_display = ""
    if deadline:
        deadline_display = f"\n📅 *Deadline:* {deadline.strftime('%A, %d %b %Y at %I:%M %p')}"

    await update.message.reply_text(
        f"✅ *Order #{order['order_number']} created!*\n\n"
        f"👤 *Customer:* {customer['name']}\n"
        f"📦 *Items:*\n{items_display}"
        f"{deadline_display}",
        parse_mode="Markdown",
        reply_markup=order_actions_keyboard(order["order_number"]),
    )

    # Clear user data
    context.user_data.pop("new_order_customer", None)
    context.user_data.pop("new_order_items_text", None)

    return ConversationHandler.END


async def neworder_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the order creation wizard."""
    context.user_data.pop("new_order_customer", None)
    context.user_data.pop("new_order_items_text", None)

    await update.message.reply_text("Order creation cancelled.")
    return ConversationHandler.END


# Build the ConversationHandler for /neworder
neworder_conversation = ConversationHandler(
    entry_points=[CommandHandler("neworder", neworder_start)],
    states={
        CUSTOMER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, neworder_customer)],
        ORDER_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, neworder_items)],
        ORDER_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, neworder_deadline)],
    },
    fallbacks=[CommandHandler("cancel", neworder_cancel)],
    name="neworder_wizard",
    persistent=False,
)


# ── /completeorder — mark order as complete ───────────────────────────


async def completeorder_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show active orders for completion selection."""
    user = update.effective_user
    order_svc = OrderService(user.id)

    orders, total = await order_svc.get_active_orders()
    if not orders:
        await update.message.reply_text("📦 No active orders to complete.")
        return

    # Build inline keyboard with active orders
    buttons = []
    for order in orders:
        order_num = order.get("order_number", "?")
        customer = order.get("customer_name", "?")
        items = ", ".join(
            i.get("name", "?") for i in order.get("items", [])
        )
        buttons.append([
            InlineKeyboardButton(
                f"✅ {order_num} — {customer} ({items})",
                callback_data=f"order:complete:{order_num}",
            )
        ])

    await update.message.reply_text(
        "Select an order to mark as *completed*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── /cancelorder — cancel an order ────────────────────────────────────


async def cancelorder_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show active orders for cancellation selection."""
    user = update.effective_user
    order_svc = OrderService(user.id)

    orders, total = await order_svc.get_active_orders()
    if not orders:
        await update.message.reply_text("📦 No active orders to cancel.")
        return

    buttons = []
    for order in orders:
        order_num = order.get("order_number", "?")
        customer = order.get("customer_name", "?")
        buttons.append([
            InlineKeyboardButton(
                f"❌ {order_num} — {customer}",
                callback_data=f"order:cancel:{order_num}",
            )
        ])

    await update.message.reply_text(
        "Select an order to *cancel*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── Shared helper: format + send order detail ─────────────────────────


async def _send_order_detail(reply_fn, order: dict) -> None:
    """Format and send a detailed order view."""
    order_num = order.get("order_number", "?")
    status = order.get("status", "pending")
    emoji = STATUS_EMOJI.get(status, "⚪")
    pay_status = order.get("payment_status", "unpaid")
    pay_emoji = PAYMENT_EMOJI.get(pay_status, "⚪")

    items_text = "\n".join(
        f"  • {i.get('quantity', 1)}× {i.get('name', '?')}"
        f"{' — ₹' + str(i['total_price']) if i.get('total_price') else ''}"
        for i in order.get("items", [])
    )

    deadline_text = ""
    if order.get("deadline"):
        dl = order["deadline"]
        deadline_text = f"\n📅 *Deadline:* {dl.strftime('%A, %d %b %Y at %I:%M %p')}"

    instructions = ""
    if order.get("special_instructions"):
        instructions = f"\n📝 *Notes:* {order['special_instructions']}"

    total_text = ""
    if order.get("total_amount", 0) > 0:
        total_text = (
            f"\n\n💰 *Total:* ₹{order['total_amount']:.2f}\n"
            f"💳 *Paid:* ₹{order.get('amount_paid', 0):.2f}\n"
            f"{pay_emoji} *Payment:* {pay_status.title()}"
        )
    else:
        total_text = f"\n\n{pay_emoji} *Payment:* {pay_status.title()}"

    created_at = order.get("created_at")
    created_text = ""
    if created_at:
        created_text = f"\n🕐 *Created:* {created_at.strftime('%d %b %Y %I:%M %p')}"

    await reply_fn(
        f"📋 *Order #{order_num}*\n\n"
        f"{emoji} *Status:* {status.replace('_', ' ').title()}\n"
        f"👤 *Customer:* {order.get('customer_name', '?')}\n"
        f"📦 *Items:*\n{items_text}"
        f"{deadline_text}"
        f"{instructions}"
        f"{total_text}"
        f"{created_text}",
        parse_mode="Markdown",
        reply_markup=order_actions_keyboard(order_num),
    )


# ── /invoice <number> — generate and send PDF invoice ─────────────────────────────

async def invoice_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Generate and send PDF invoice for an order."""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "Please specify an order number: `/invoice ORD-2024-0001`",
            parse_mode="Markdown",
        )
        return
        
    order_number = context.args[0].upper()
    if not order_number.startswith("ORD-"):
        order_number = f"ORD-{order_number}"
        
    order_svc = OrderService(user.id)
    order = await order_svc.get_order(order_number)
    
    if not order:
        await update.message.reply_text(f"❌ Order {order_number} not found.")
        return
        
    business = await businesses_col().find_one({"telegram_user_id": user.id})
    if not business:
        await update.message.reply_text("Business profile not found.")
        return
        
    from app.services.invoice_service import invoice_service
    pdf_bytes = invoice_service.generate_invoice_pdf(business, order)
    
    await context.bot.send_document(
        chat_id=user.id,
        document=pdf_bytes,
        filename=f"Invoice_{order_number}.pdf",
        caption=f"Here is the invoice for Order {order_number}."
    )

