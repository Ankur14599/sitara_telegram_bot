import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.core.database import db

logger = logging.getLogger(__name__)

async def broadcast_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Broadcast a message to all customers of a business with a known Telegram handle."""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "Please provide a message to broadcast:\n"
            "`/broadcast Hello everyone! 10% off this weekend.`",
            parse_mode="Markdown",
        )
        return
        
    message = " ".join(context.args)
    
    # Get all customers for this business
    customers = await db.customers.find({
        "business_id": user.id,
        "telegram_username": {"$exists": True, "$ne": None}
    }).to_list(None)
    
    if not customers:
        await update.message.reply_text("No customers with Telegram usernames found.")
        return
        
    await update.message.reply_text(f"Broadcasting to {len(customers)} customers... This may take a moment.")
    
    success_count = 0
    fail_count = 0
    
    for customer in customers:
        try:
            # We assume telegram_username is an ID or @username we can send to
            target = customer["telegram_username"]
            if not str(target).startswith("@") and not str(target).isdigit():
                target = f"@{target}"
                
            await context.bot.send_message(
                chat_id=target,
                text=f"📢 *Message from your seller:*\n\n{message}",
                parse_mode="Markdown"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to broadcast to {customer.get('telegram_username')}: {e}")
            fail_count += 1
            
        # Rate limit: 1 msg per sec
        await asyncio.sleep(1)
        
    await update.message.reply_text(
        f"✅ Broadcast complete.\n"
        f"Sent successfully: {success_count}\n"
        f"Failed: {fail_count}"
    )
