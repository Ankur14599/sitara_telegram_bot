"""
BOM command handlers — /bom, /boms, /setbom (guided wizard).
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.services.bom_service import BOMService
from app.services.groq_service import groq_service

logger = logging.getLogger(__name__)


# ── /boms — List all products with a BOM ──────────────────────────────


async def boms_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """List all products that have a defined BOM."""
    user = update.effective_user
    bom_svc = BOMService(user.id)

    boms = await bom_svc.get_all_boms()

    if not boms:
        await update.message.reply_text(
            "🧾 You don't have any Bill of Materials defined yet.\n\n"
            "Define materials for a product using:\n"
            "`/setbom chocolate cake`",
            parse_mode="Markdown",
        )
        return

    lines = ["🧾 *Product Materials (BOMs)*\n"]

    for bom in boms:
        product = bom.get("product_name_normalized", "?").title()
        confirmed = "✅" if bom.get("confirmed") else "⏳"
        mat_count = len(bom.get("materials", []))

        lines.append(f"• {confirmed} *{product}* ({mat_count} materials)")

    lines.append("\nUse `/bom <product>` to see exact materials.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# ── /bom <product> — View specific BOM ────────────────────────────────


async def bom_detail_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """View the materials for a specific product."""
    if not context.args:
        await update.message.reply_text(
            "Please specify the product name.\n"
            "Example: `/bom chocolate cake`",
            parse_mode="Markdown",
        )
        return

    product_name = " ".join(context.args)
    user = update.effective_user
    bom_svc = BOMService(user.id)

    bom = await bom_svc.check_bom(product_name)

    if not bom:
        await update.message.reply_text(
            f"❌ No materials defined for '{product_name.title()}'.\n"
            f"Use `/setbom {product_name}` to set them up.",
            parse_mode="Markdown",
        )
        return

    message = bom_svc.format_bom_display(bom)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Materials", callback_data=f"bom:edit:{bom['product_name_normalized']}")]
    ])
    
    await update.message.reply_text(
        message, 
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ── /setbom — Guided Wizard ───────────────────────────────────────────

# ConversationHandler states
BOM_MATERIALS = 0
BOM_CONFIRM = 1


async def setbom_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the /setbom wizard."""
    if context.args:
        product_name = " ".join(context.args)
        context.user_data["bom_product_name"] = product_name
    else:
        # Require argument for now, or could ask in a separate step
        await update.message.reply_text(
            "Please specify the product name.\n"
            "Example: `/setbom chocolate cake`",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"📝 *Setting Materials for {product_name.title()}*\n\n"
        f"What inventory does making 1 {product_name.title()} consume?\n\n"
        f"Example: _200g flour, 2 eggs, 100g butter, 50g cocoa powder_\n\n"
        f"Reply with the materials, or type /cancel to abort.",
        parse_mode="Markdown",
    )
    return BOM_MATERIALS


async def setbom_materials(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive materials description and extract with NLP."""
    message_text = update.message.text.strip()
    product_name = context.user_data.get("bom_product_name", "Unknown")
    
    await update.message.reply_chat_action("typing")
    
    # Extract materials via GROQ
    materials = await groq_service.extract_materials(message_text)
    
    if not materials:
        await update.message.reply_text(
            "❌ Sorry, I couldn't understand those materials.\n"
            "Please try again using a format like:\n"
            "_200g flour, 2 pieces egg, 100g butter_\n\n"
            "Or type /cancel to abort.",
            parse_mode="Markdown"
        )
        return BOM_MATERIALS
        
    # Store extracted materials in context
    context.user_data["bom_extracted_materials"] = materials
    
    # Build confirmation message
    lines = [f"Got it! 1 *{product_name.title()}* uses:"]
    for mat in materials:
        name = mat.get("item", "?").title()
        qty = mat.get("quantity", 0)
        unit = mat.get("unit", "pieces")
        lines.append(f"• {qty}{unit} {name}")
        
    lines.append("\nDoes this look correct?")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm & Save", callback_data="bom_wizard:confirm"),
            InlineKeyboardButton("✏️ Try Again", callback_data="bom_wizard:retry")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="bom_wizard:cancel")]
    ])
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    return BOM_CONFIRM


async def setbom_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the confirmation inline keyboard for BOM wizard."""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "retry":
        await query.edit_message_text(
            "Okay, let's try again. What materials does it consume?\n"
            "Example: _200g flour, 2 eggs_"
        )
        return BOM_MATERIALS
        
    elif action == "cancel":
        await query.edit_message_text("❌ BOM setup cancelled.")
        context.user_data.pop("bom_product_name", None)
        context.user_data.pop("bom_extracted_materials", None)
        return ConversationHandler.END
        
    elif action == "confirm":
        user = update.effective_user
        product_name = context.user_data.get("bom_product_name")
        materials = context.user_data.get("bom_extracted_materials", [])
        
        bom_svc = BOMService(user.id)
        
        # Save BOM as confirmed
        await bom_svc.create_or_update_bom(
            product_name=product_name,
            materials=materials,
            confirmed=True
        )
        
        await query.edit_message_text(
            f"✅ Materials for *{product_name.title()}* saved successfully!\n"
            f"Inventory will now auto-deduct when this is ordered.",
            parse_mode="Markdown"
        )
        
        context.user_data.pop("bom_product_name", None)
        context.user_data.pop("bom_extracted_materials", None)
        return ConversationHandler.END
        
    return BOM_CONFIRM


async def setbom_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the BOM creation wizard."""
    context.user_data.pop("bom_product_name", None)
    context.user_data.pop("bom_extracted_materials", None)
    await update.message.reply_text("BOM setup cancelled.")
    return ConversationHandler.END


# Build the ConversationHandler
bom_conversation = ConversationHandler(
    entry_points=[CommandHandler("setbom", setbom_start)],
    states={
        BOM_MATERIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, setbom_materials)],
        BOM_CONFIRM: [CallbackQueryHandler(setbom_callback, pattern="^bom_wizard:")],
    },
    fallbacks=[CommandHandler("cancel", setbom_cancel)],
    name="setbom_wizard",
    persistent=False,
)
