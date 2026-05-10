"""
Inventory command handlers — /inventory, /addstock, /removestock, /lowstock, etc.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.services.inventory_service import InventoryService
from app.models.inventory import DeductionSource

logger = logging.getLogger(__name__)


async def inventory_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """View full inventory with quantities and thresholds."""
    user = update.effective_user
    inv_svc = InventoryService(user.id)

    items = await inv_svc.get_all_items()

    if not items:
        await update.message.reply_text(
            "📊 Your inventory is currently empty.\n\n"
            "Add stock by typing:\n"
            "_\"added 10kg flour\"_ or use /addstock",
            parse_mode="Markdown",
        )
        return

    lines = ["📊 *Current Inventory*\n"]

    for item in items:
        name = item.get("name", "Unknown")
        qty = item.get("quantity", 0)
        unit = item.get("unit", "pieces")
        threshold = item.get("low_stock_threshold", 5)

        alert = ""
        if qty <= threshold:
            alert = " ⚠️ LOW"

        lines.append(f"• *{name}:* {qty}{unit} _(threshold: {threshold}){alert}_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


async def addstock_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /addstock command."""
    if not context.args:
        await update.message.reply_text(
            "Please specify the item and quantity.\n"
            "Example: `/addstock flour 10 kg`",
            parse_mode="Markdown",
        )
        return

    # Let the natural language orchestrator handle this via GROQ
    # by pretending the user just typed "added X Y"
    from app.bot.handlers.natural_language import natural_language_handler
    
    # Prepend "added " to force the intent classification
    message_text = "added " + " ".join(context.args)
    update.message.text = message_text
    
    await natural_language_handler(update, context)


async def removestock_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /removestock command."""
    if not context.args:
        await update.message.reply_text(
            "Please specify the item and quantity.\n"
            "Example: `/removestock eggs 3 pieces`",
            parse_mode="Markdown",
        )
        return

    # Delegate to NLP handler
    from app.bot.handlers.natural_language import natural_language_handler
    
    message_text = "used " + " ".join(context.args)
    update.message.text = message_text
    
    await natural_language_handler(update, context)


async def lowstock_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """View items that are at or below their low-stock threshold."""
    user = update.effective_user
    inv_svc = InventoryService(user.id)

    items = await inv_svc.get_low_stock_items()

    if not items:
        await update.message.reply_text("✅ All inventory levels are looking good!")
        return

    lines = ["⚠️ *Low Stock Items*\n"]
    for item in items:
        name = item.get("name", "?")
        qty = item.get("quantity", 0)
        unit = item.get("unit", "pieces")
        threshold = item.get("low_stock_threshold", 5)

        lines.append(f"• *{name}:* {qty}{unit} _(threshold: {threshold})_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


async def setprice_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Set the selling price for an item."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Please specify the item and price.\n"
            "Example: `/setprice cake 500`",
            parse_mode="Markdown",
        )
        return

    try:
        price = float(context.args[-1])
        item_name = " ".join(context.args[:-1])
    except ValueError:
        await update.message.reply_text("❌ The price must be a number.")
        return

    user = update.effective_user
    inv_svc = InventoryService(user.id)

    result = await inv_svc.set_price(item_name, price)

    if result:
        await update.message.reply_text(
            f"✅ Selling price for *{result['name']}* set to {price}.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Item '{item_name}' not found in inventory."
        )


async def setthreshold_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Set the low-stock threshold for an item."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Please specify the item and threshold.\n"
            "Example: `/setthreshold flour 5`",
            parse_mode="Markdown",
        )
        return

    try:
        threshold = float(context.args[-1])
        item_name = " ".join(context.args[:-1])
    except ValueError:
        await update.message.reply_text("❌ The threshold must be a number.")
        return

    user = update.effective_user
    inv_svc = InventoryService(user.id)

    result = await inv_svc.set_threshold(item_name, threshold)

    if result:
        unit = result.get("unit", "pieces")
        await update.message.reply_text(
            f"✅ Low-stock threshold for *{result['name']}* set to {threshold}{unit}.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Item '{item_name}' not found in inventory."
        )
