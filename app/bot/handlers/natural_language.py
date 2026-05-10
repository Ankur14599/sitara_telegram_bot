"""
Natural language message orchestrator — the core handler.
Routes free-form messages through: intent → extraction → service → response.
Sitara (the AI assistant) handles greetings, chitchat, and open questions conversationally.
"""

import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.database import businesses_col
from app.services.groq_service import groq_service
from app.services.order_service import OrderService
from app.services.customer_service import CustomerService
from app.services.inventory_service import InventoryService
from app.services.reminder_service import ReminderService
from app.services.bom_service import BOMService
from app.services.trend_service import TrendService
from app.bot.keyboards.order_keyboards import order_actions_keyboard

logger = logging.getLogger(__name__)


async def natural_language_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None
) -> None:
    """
    Handle free-form text messages.
    Pipeline: classify intent → extract entities → execute action → respond.
    Greetings and chitchat are handled by Sitara directly.
    """
    user = update.effective_user
    if message_text is None:
        message_text = update.message.text.strip()

    if not message_text:
        return

    # Get business context
    business = await businesses_col().find_one({"telegram_user_id": user.id})
    if not business:
        await update.message.reply_text(
            "❌ You haven't registered yet! Please use /start to set up your business."
        )
        return

    business_id = user.id
    tz = business.get("timezone", "Asia/Kolkata")

    if _is_trend_question(message_text):
        await _handle_trend_question(update, context, business_id, message_text)
        return

    # ── Per-user GROQ rate-limit check ───────────────────────────────
    if not groq_service.check_user_rate_limit(user.id):
        from app.core.config import settings
        window_mins = settings.GROQ_USER_WINDOW_SECONDS // 60
        await update.message.reply_text(
            f"⏳ *Sitara needs a breather!*\n\n"
            f"You've reached the AI request limit ({settings.GROQ_USER_CALLS_PER_WINDOW} calls "
            f"per {window_mins} minutes). This helps keep the service fast for everyone.\n\n"
            f"You can still use any /command while you wait! 😊",
            parse_mode="Markdown",
        )
        return

    # Step 1: Classify intent (this counts as 1 GROQ call)
    await update.message.reply_chat_action("typing")
    groq_service.record_user_call(user.id)
    intent = await groq_service.classify_intent(message_text)

    logger.info(f"Intent classified: '{intent}' for user {user.id}, message: '{message_text[:60]}'")

    # Step 2: Route to appropriate handler based on intent
    try:
        if intent == "greeting":
            await _handle_greeting(update, context, business, message_text)

        elif intent == "chitchat":
            await _handle_chitchat(update, context, business, message_text)

        elif intent == "new_order":
            groq_service.record_user_call(user.id)  # extraction = 2nd call
            await _handle_new_order(update, context, business_id, tz, message_text)

        elif intent == "update_order":
            await _handle_update_order(update, context, business_id, message_text)

        elif intent == "check_order":
            await _handle_check_order(update, context, business_id, message_text)

        elif intent == "add_stock":
            groq_service.record_user_call(user.id)  # extraction = 2nd call
            await _handle_stock_update(update, context, business_id, message_text, "add")

        elif intent == "remove_stock":
            groq_service.record_user_call(user.id)  # extraction = 2nd call
            await _handle_stock_update(update, context, business_id, message_text, "remove")

        elif intent == "set_recipe":
            await _handle_set_recipe(update, context, business_id, message_text)

        elif intent == "question":
            await _handle_question(update, context, business, message_text)

        else:
            # Unknown — let Sitara respond gracefully rather than a rigid error
            await _handle_unknown(update, context, business, message_text)

    except Exception as e:
        logger.error(f"Error handling '{intent}' intent: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, something went wrong processing your message. Please try again."
        )


# ── Sitara conversational handlers ────────────────────────────────────


async def _handle_greeting(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business: dict,
    message_text: str,
) -> None:
    """Respond to greetings warmly as Sitara."""
    owner_name = business.get("owner_name", "there")
    biz_name = business.get("business_name", "your business")

    # Use Sitara to generate a warm, personalised greeting
    prompt = (
        f"The user just greeted you with: \"{message_text}\". "
        f"Greet them warmly by name ({owner_name}), introduce yourself as Sitara, "
        f"their business assistant for '{biz_name}', and briefly mention 1-2 things you can help with. "
        f"Keep it short, friendly, and natural."
    )
    reply = await groq_service.chat_with_sitara(prompt, update.effective_user.id, business)
    await update.message.reply_text(reply)


async def _handle_chitchat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business: dict,
    message_text: str,
) -> None:
    """Handle casual conversation as Sitara."""
    reply = await groq_service.chat_with_sitara(message_text, update.effective_user.id, business)
    await update.message.reply_text(reply)


async def _handle_unknown(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business: dict,
    message_text: str,
) -> None:
    """Let Sitara handle unrecognised messages gracefully instead of a rigid error."""
    prompt = (
        f"The user said: \"{message_text}\". "
        "You're not sure what they mean in a business context. "
        "Respond warmly, acknowledge what they said, and gently guide them "
        "towards what you can help with (orders, inventory, payments, reports). "
        "Mention they can type /help to see all commands."
    )
    reply = await groq_service.chat_with_sitara(prompt, update.effective_user.id, business)
    await update.message.reply_text(reply)


# ── Business intent handlers ───────────────────────────────────────────


def _is_trend_question(message_text: str) -> bool:
    """Detect common trend/report questions without spending an AI call."""
    text = message_text.lower()
    keywords = [
        "trend", "trending", "most ordered", "top item", "top product",
        "best seller", "bestseller", "popular item", "top customer",
        "best customer", "repeat customer", "customer trend",
    ]
    return any(keyword in text for keyword in keywords)


async def _handle_trend_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    message_text: str,
) -> None:
    """Answer trend questions from live order data."""
    text = message_text.lower()
    days = 30

    if "today" in text:
        days = 1
    elif "week" in text or "7 day" in text:
        days = 7
    elif "month" in text or "30 day" in text:
        days = 30
    elif "90 day" in text or "quarter" in text:
        days = 90

    trends = await TrendService(business_id).get_trends(days=days)
    await update.message.reply_text(
        TrendService.format_trends(trends),
        parse_mode="Markdown",
    )


async def _handle_new_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    timezone_str: str,
    message_text: str,
) -> None:
    """Handle new_order intent: extract → create customer → create order → confirm."""

    # Extract order data
    order_data = await groq_service.extract_order(message_text, timezone_str)

    if not order_data:
        await update.message.reply_text(
            "❌ Sorry, I couldn't understand the order details from your message.\n"
            "Please try again with more details, like:\n"
            "_\"order for Priya for 2 cakes by friday 8pm\"_",
            parse_mode="Markdown",
        )
        return

    if not order_data.get("is_valid_order", False):
        reason = order_data.get("reason_if_invalid", "Not enough information")
        customer_name = order_data.get("customer_name")

        reply = f"⚠️ I couldn't create a valid order: {reason}\n\n"

        if customer_name and customer_name != "Unknown Customer":
            # Quick Reorder Suggestion
            customer_svc = CustomerService(business_id)
            customer = await customer_svc.find_or_create(customer_name)

            from app.core.database import db
            last_order = await db.orders.find_one(
                {"business_id": business_id, "customer_id": str(customer["_id"])},
                sort=[("created_at", -1)]
            )
            if last_order:
                items_str = ", ".join(f"{i.get('quantity')}x {i.get('name')}" for i in last_order.get("items", []))
                reply += (
                    f"💡 *Quick Reorder for {customer['name']}?*\n"
                    f"Last time they ordered: {items_str} (₹{last_order.get('total_amount', 0)})\n"
                    f"Type _\"same again for Priya\"_ or use /neworder to modify."
                )
            else:
                reply += "Please specify what they want to order."
        else:
            reply += (
                "Please include at least:\n"
                "• Customer name\n"
                "• What they want to order\n\n"
                "Example: _\"order for Priya for 2 cakes by friday\"_"
            )

        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    customer_name = order_data.get("customer_name", "Unknown Customer")
    items = order_data.get("items", [])
    deadline_str = order_data.get("deadline")
    special_instructions = order_data.get("special_instructions")

    # Parse deadline
    deadline = None
    if deadline_str:
        try:
            if isinstance(deadline_str, str):
                from dateutil.parser import parse as dateparse
                deadline = dateparse(deadline_str)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
            elif isinstance(deadline_str, datetime):
                deadline = deadline_str
        except Exception as e:
            logger.warning(f"Failed to parse deadline '{deadline_str}': {e}")

    # Find or create customer
    customer_svc = CustomerService(business_id)
    customer = await customer_svc.find_or_create(customer_name)
    customer_id = str(customer["_id"])

    # Create the order
    order_svc = OrderService(business_id)
    order = await order_svc.create_order(
        customer_name=customer["name"],
        items=items,
        deadline=deadline,
        deadline_raw=order_data.get("deadline_raw") or deadline_str,
        special_instructions=special_instructions,
        original_message=message_text,
        customer_id=customer_id,
    )

    order_number = order["order_number"]

    # Increment customer stats
    await customer_svc.increment_order_stats(customer_name)

    # Schedule reminders if deadline exists
    if deadline:
        reminder_svc = ReminderService(business_id)
        await reminder_svc.schedule_reminders(
            order_id=str(order["_id"]),
            order_number=order_number,
            deadline=deadline,
        )

    # Build confirmation message
    items_text = "\n".join(
        f"  • {item.get('quantity', 1)}× {item.get('name', '?')}"
        for item in items
    )

    deadline_text = ""
    if deadline:
        deadline_text = f"\n📅 *Deadline:* {deadline.strftime('%A, %d %b %Y at %I:%M %p')}"

    instructions_text = ""
    if special_instructions:
        instructions_text = f"\n📝 *Notes:* {special_instructions}"

    confidence = order_data.get("deadline_confidence", "")
    confidence_text = ""
    if confidence and confidence != "high":
        confidence_text = f"\n⚠️ _Deadline confidence: {confidence} — please verify_"

    # Check BOM for each item
    bom_svc = BOMService(business_id)
    bom_messages = []
    for item in items:
        item_name = item.get("name", "")
        bom = await bom_svc.check_bom(item_name)

        if bom and bom.get("confirmed"):
            # Preview deduction
            qty = item.get("quantity", 1)
            deduction_preview = []
            for mat in bom.get("materials", []):
                total_qty = mat["quantity_per_unit"] * qty
                deduction_preview.append(
                    f"{total_qty}{mat.get('unit', 'pieces')} {mat['inventory_item_name']}"
                )
            if deduction_preview:
                bom_messages.append(
                    f"📦 On completion, will deduct: {', '.join(deduction_preview)}"
                )
        elif not bom:
            # BOM missing — prompt learning
            bom_messages.append(
                f"ℹ️ I don't know what materials 1 {item_name.title()} uses yet.\n"
                f"Use /setbom {item_name} to define its materials."
            )

    bom_text = "\n\n".join(bom_messages) if bom_messages else ""

    reply = (
        f"✅ *Order #{order_number} created!*\n\n"
        f"👤 *Customer:* {customer['name']}\n"
        f"📦 *Items:*\n{items_text}"
        f"{deadline_text}"
        f"{instructions_text}"
        f"{confidence_text}"
    )

    if bom_text:
        reply += f"\n\n{bom_text}"

    await update.message.reply_text(
        reply,
        parse_mode="Markdown",
        reply_markup=order_actions_keyboard(order_number),
    )


async def _handle_stock_update(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    message_text: str,
    direction: str,
) -> None:
    """Handle add_stock / remove_stock intents."""

    # Extract inventory update data
    inv_data = await groq_service.extract_inventory_update(message_text)

    if not inv_data:
        await update.message.reply_text(
            "❌ Sorry, I couldn't understand the inventory update.\n"
            "Try something like:\n"
            "_\"added 10kg flour\"_ or _\"used 3 eggs\"_",
            parse_mode="Markdown",
        )
        return

    item_name = inv_data.get("item", "")
    quantity = inv_data.get("quantity", 0)
    unit = inv_data.get("unit", "pieces")
    actual_direction = inv_data.get("direction", direction)

    inv_svc = InventoryService(business_id)

    if actual_direction == "add":
        result = await inv_svc.add_stock(item_name, quantity, unit)
        if result:
            old_qty = result["quantity"] - quantity
            await update.message.reply_text(
                f"✅ *{item_name.title()}* updated: "
                f"{old_qty}{unit} → {result['quantity']}{unit}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"✅ *{item_name.title()}* added to inventory: {quantity}{unit}",
                parse_mode="Markdown",
            )
    else:
        result = await inv_svc.deduct_stock(item_name, quantity)
        if result:
            old_qty = result["quantity"] + quantity
            reply = (
                f"✅ *{item_name.title()}* updated: "
                f"{old_qty}{unit} → {result['quantity']}{unit}"
            )

            # Check for low stock
            if await inv_svc.check_low_stock(result):
                threshold = result.get("low_stock_threshold", 5)
                reply += (
                    f"\n\n⚠️ *Low Stock Alert!* "
                    f"{item_name.title()} is below threshold ({threshold}{unit})"
                )
                await inv_svc.mark_low_stock_alerted(str(result["_id"]))

            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"⚠️ Item *{item_name.title()}* not found in your inventory.\n"
                f"Use _\"added {quantity}{unit} {item_name}\"_ to add it first.",
                parse_mode="Markdown",
            )


async def _handle_check_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    message_text: str,
) -> None:
    """Handle check_order intent — show order status or summary."""
    order_svc = OrderService(business_id)

    # Try to find specific order number in the message
    import re
    order_match = re.search(r"ORD-\d{4}-\d{4}", message_text, re.IGNORECASE)

    if order_match:
        order_number = order_match.group().upper()
        order = await order_svc.get_order(order_number)

        if order:
            items_text = "\n".join(
                f"  • {i.get('quantity', 1)}× {i.get('name', '?')}"
                for i in order.get("items", [])
            )
            status_emoji = {
                "pending": "🟡", "in_progress": "🔵",
                "ready": "🟢", "completed": "✅", "cancelled": "❌",
            }
            status = order.get("status", "pending")
            emoji = status_emoji.get(status, "⚪")

            deadline_text = ""
            if order.get("deadline"):
                dl = order["deadline"]
                deadline_text = f"\n📅 *Deadline:* {dl.strftime('%A, %d %b %Y at %I:%M %p')}"

            await update.message.reply_text(
                f"📋 *Order #{order_number}*\n\n"
                f"{emoji} *Status:* {status.replace('_', ' ').title()}\n"
                f"👤 *Customer:* {order.get('customer_name', '?')}\n"
                f"📦 *Items:*\n{items_text}"
                f"{deadline_text}\n"
                f"💰 *Payment:* {order.get('payment_status', 'unpaid').title()}",
                parse_mode="Markdown",
                reply_markup=order_actions_keyboard(order_number),
            )
        else:
            await update.message.reply_text(
                f"❌ Order {order_number} not found."
            )
    else:
        # General inquiry — show active orders summary
        orders, total = await order_svc.get_active_orders()
        if orders:
            await update.message.reply_text(
                f"📦 You have *{total} active order(s)*.\n"
                f"Use /orders to see details.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "📦 You have no active orders right now."
            )


async def _handle_update_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    message_text: str,
) -> None:
    """Handle update_order intent."""
    await update.message.reply_text(
        "To update an order, please use one of these commands:\n\n"
        "✅ /completeorder — Mark an order as complete\n"
        "❌ /cancelorder — Cancel an order\n\n"
        "Or click the action buttons on any order."
    )


async def _handle_set_recipe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business_id: int,
    message_text: str,
) -> None:
    """Handle set_recipe intent — redirect to /setbom."""
    await update.message.reply_text(
        "To define materials for a product, use the /setbom command.\n\n"
        "Example: `/setbom chocolate cake`\n\n"
        "This will guide you through listing the materials needed per unit.",
        parse_mode="Markdown",
    )


async def _handle_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    business: dict,
    message_text: str,
) -> None:
    """
    Handle general business questions.
    Pulls live stats and lets Sitara answer in a conversational way.
    """
    business_id = update.effective_user.id
    order_svc = OrderService(business_id)
    inv_svc = InventoryService(business_id)

    # Gather quick stats
    active_orders, total_orders = await order_svc.get_active_orders()
    low_stock = await inv_svc.get_low_stock_items()
    todays = await order_svc.get_todays_orders()

    # Let Sitara answer with context injected
    stats_context = (
        f"Current business stats — "
        f"Active orders: {total_orders}, "
        f"Orders today: {len(todays)}, "
        f"Low stock items: {len(low_stock)}. "
        f"The user asked: \"{message_text}\". "
        "Answer their question using this data in a helpful, conversational way. "
        "If the data doesn't directly answer, give the stats overview and suggest /summary for more detail."
    )

    reply = await groq_service.chat_with_sitara(stats_context, update.effective_user.id, business)
    await update.message.reply_text(reply, parse_mode="Markdown")
