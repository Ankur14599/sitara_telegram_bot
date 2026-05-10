from telegram import Update
from telegram.ext import ContextTypes

from app.services.summary_service import SummaryService

async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /summary command."""
    business_id = update.effective_user.id
    summary_svc = SummaryService(business_id)

    text = await summary_svc.get_daily_summary()
    await update.message.reply_text(text, parse_mode="Markdown")

async def weeklysummary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /weeklysummary command."""
    business_id = update.effective_user.id
    summary_svc = SummaryService(business_id)

    text = await summary_svc.get_weekly_summary()
    await update.message.reply_text(text, parse_mode="Markdown")
