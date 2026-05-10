import re
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from app.services.payment_service import PaymentService
from app.services.order_service import OrderService
from app.models.payment import PaymentMethod

async def record_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /recordpayment command."""
    business_id = update.effective_user.id
    payment_svc = PaymentService(business_id)
    order_svc = OrderService(business_id)

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /recordpayment <order_number> <amount> [method]\n"
            "Methods: cash, upi, card, other\n"
            "Example: /recordpayment ORD-2024-001 500 upi"
        )
        return

    order_number = context.args[0].upper()
    if not order_number.startswith("ORD-"):
        order_number = f"ORD-{order_number}"
    
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    method_str = context.args[2].lower() if len(context.args) > 2 else "cash"
    try:
        method = PaymentMethod(method_str)
    except ValueError:
        method = PaymentMethod.CASH

    # Get order ID from order number
    order = await order_svc.get_order(order_number)
    if not order:
        await update.message.reply_text(f"Order {order_number} not found.")
        return

    order_id = str(order["_id"])
    
    success, msg = await payment_svc.record_payment(order_id, amount, method)
    await update.message.reply_text(msg)

async def unpaid_orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /unpaid command."""
    business_id = update.effective_user.id
    payment_svc = PaymentService(business_id)

    unpaid_orders = await payment_svc.get_unpaid_orders()
    
    if not unpaid_orders:
        await update.message.reply_text("No unpaid or partially paid orders.")
        return

    lines = ["📝 *Unpaid Orders*"]
    total_outstanding = 0.0
    for order in unpaid_orders:
        outstanding = order.total_amount - order.amount_paid
        total_outstanding += outstanding
        lines.append(f"• {order.order_number}: ₹{outstanding:.2f} due (Total: ₹{order.total_amount:.2f}) - {order.customer_name}")

    lines.append(f"\n*Total Outstanding:* ₹{total_outstanding:.2f}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def revenue_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /revenue command."""
    business_id = update.effective_user.id
    payment_svc = PaymentService(business_id)

    now = datetime.now(timezone.utc)
    
    # Calculate start of today, week, month
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    today_rev = await payment_svc.get_revenue_summary(today_start, now)
    week_rev = await payment_svc.get_revenue_summary(week_start, now)
    month_rev = await payment_svc.get_revenue_summary(month_start, now)

    text = (
        "💰 *Revenue Summary*\n\n"
        f"• *Today:* ₹{today_rev['total_collected']:.2f}\n"
        f"• *This Week:* ₹{week_rev['total_collected']:.2f}\n"
        f"• *This Month:* ₹{month_rev['total_collected']:.2f}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")
