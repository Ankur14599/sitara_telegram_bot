from telegram import Update
from telegram.ext import ContextTypes

from app.services.summary_service import SummaryService
from app.services.trend_service import TrendService

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


async def trends_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /trends command."""
    business_id = update.effective_user.id
    days = 30

    if context.args:
        arg = context.args[0].lower()
        if arg in {"today", "1"}:
            days = 1
        elif arg in {"week", "7"}:
            days = 7
        elif arg in {"month", "30"}:
            days = 30
        elif arg in {"quarter", "90"}:
            days = 90

    trends = await TrendService(business_id).get_trends(days=days)
    await update.message.reply_text(
        TrendService.format_trends(trends),
        parse_mode="Markdown",
    )
