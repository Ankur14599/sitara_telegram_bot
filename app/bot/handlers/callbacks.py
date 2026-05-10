"""
InlineKeyboard callback router.
Dispatches callback queries from inline buttons.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.services.order_service import OrderService
from app.services.bom_service import BOMService

logger = logging.getLogger(__name__)


async def callback_router(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Route callback queries to appropriate handlers based on data format.
    Format is typically: domain:action:id
    """
    query = update.callback_query
    user = update.effective_user
    business_id = user.id

    # The prefix (e.g. "order:complete:ORD-1234")
    data = query.data
    logger.info(f"Received callback: {data} from user {user.id}")

    try:
        parts = data.split(":")
        domain = parts[0]
        action = parts[1] if len(parts) > 1 else None

        # ── Orders ────────────────────────────────────────────────────────
        if domain == "order":
            order_number = parts[2] if len(parts) > 2 else None
            await _handle_order_callback(query, context, business_id, action, order_number)

        # ── Pagination ────────────────────────────────────────────────────
        elif domain == "page":
            target = parts[1]
            page_num = int(parts[2])
            await _handle_pagination_callback(query, context, business_id, target, page_num)

        # ── Main Menu ─────────────────────────────────────────────────────
        elif domain == "menu":
            target = parts[1]
            await _handle_menu_callback(query, context, business_id, target)

        else:
            # Let it pass if handled by ConversationHandler (e.g., bom_wizard)
            if not data.startswith("bom_wizard:"):
                await query.answer("Unknown action.")

    except Exception as e:
        logger.error(f"Error handling callback {data}: {e}", exc_info=True)
        await query.answer("❌ Error processing request.", show_alert=True)


# ── Order Callbacks ───────────────────────────────────────────────────


async def _handle_order_callback(
    query, context, business_id: int, action: str, order_number: str
) -> None:
    """Handle order-related inline button callbacks."""
    from app.bot.handlers.orders import _send_order_detail
    from app.bot.keyboards.order_keyboards import order_confirm_keyboard, order_actions_keyboard

    order_svc = OrderService(business_id)

    if action == "view":
        order = await order_svc.get_order(order_number)
        if order:
            await query.answer()
            # Send as new message instead of edit to keep history
            await _send_order_detail(query.message.reply_text, order)
        else:
            await query.answer("Order not found.", show_alert=True)

    elif action == "complete":
        # Prompt confirmation
        await query.answer()
        await query.message.reply_text(
            f"Are you sure you want to mark *{order_number}* as complete?",
            parse_mode="Markdown",
            reply_markup=order_confirm_keyboard(order_number),
        )

    elif action == "cancel":
        # Prompt confirmation
        await query.answer()
        await query.message.reply_text(
            f"Are you sure you want to cancel *{order_number}*?",
            parse_mode="Markdown",
            reply_markup=order_confirm_keyboard(order_number),
        )

    elif action == "confirm_action":
        # The previous message text tells us if it was complete or cancel
        text = query.message.text.lower()
        if "complete" in text:
            order = await order_svc.complete_order(order_number)
            if order:
                msg = f"✅ Order *{order_number}* marked as complete!"
                
                # Append deduction report if any
                deduction_report = order.get("_deduction_report")
                if deduction_report:
                    bom_svc = BOMService(business_id)
                    report_text = bom_svc.format_deduction_report(deduction_report)
                    msg += f"\n\n{report_text}"
                
                error = order.get("_deduction_error")
                if error:
                    msg += f"\n\n⚠️ BOM auto-deduction failed: {error}"
                    
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await query.edit_message_text(f"❌ Failed to update {order_number}.")

    elif action == "cancel_action":
        # They hit 'No, go back' on confirmation
        await query.edit_message_text(f"Action cancelled for {order_number}.")


# ── Pagination Callbacks ──────────────────────────────────────────────


async def _handle_pagination_callback(
    query, context, business_id: int, target: str, page: int
) -> None:
    """Handle pagination callbacks."""
    if target == "orders":
        from app.bot.handlers.orders import orders_handler
        # Mock the args for the handler
        context.args = [str(page)]
        # We need an Update-like object, but we are inside a query.
        # Instead of calling the handler, we can edit the message directly here, 
        # but to reuse logic, we just modify the message and call it.
        # Actually, it's easier to just call the logic.
        from app.services.order_service import ORDERS_PER_PAGE
        import math
        from app.bot.handlers.orders import STATUS_EMOJI, PAYMENT_EMOJI
        from app.bot.keyboards.order_keyboards import orders_pagination_keyboard

        order_svc = OrderService(business_id)
        orders, total = await order_svc.get_active_orders(page)
        total_pages = math.ceil(total / ORDERS_PER_PAGE)

        if not orders:
            await query.answer("No orders on this page.")
            return

        lines = [f"📦 *Active Orders* (Page {page}/{total_pages}, {total} total)\n"]

        for order in orders:
            status = order.get("status", "pending")
            emoji = STATUS_EMOJI.get(status, "⚪")
            pay_status = order.get("payment_status", "unpaid")
            pay_emoji = PAYMENT_EMOJI.get(pay_status, "⚪")
            order_num = order.get("order_number", "?")
            customer = order.get("customer_name", "?")

            items_summary = ", ".join(f"{i.get('quantity', 1)}× {i.get('name', '?')}" for i in order.get("items", []))
            
            deadline_text = ""
            if order.get("deadline"):
                deadline_text = f"\n   📅 {order['deadline'].strftime('%d %b %I:%M %p')}"

            lines.append(f"{emoji} *{order_num}* — {customer}\n   {items_summary}{deadline_text}\n   {pay_emoji} Payment: {pay_status.title()}")

        await query.edit_message_text(
            "\n\n".join(lines),
            parse_mode="Markdown",
            reply_markup=orders_pagination_keyboard(page, total_pages),
        )


# ── Main Menu Callbacks ───────────────────────────────────────────────


async def _handle_menu_callback(
    query, context, business_id: int, target: str
) -> None:
    """Handle main menu button clicks."""
    await query.answer(f"Loading {target}...")
    
    # Send a mock command text to route it
    if target == "orders":
        from app.bot.handlers.orders import orders_handler
        context.args = []
        await orders_handler(query, context)
    elif target == "inventory":
        from app.bot.handlers.inventory import inventory_handler
        await inventory_handler(query, context)
    # the rest will be implemented in later phases
