"""
Telegram bot middleware.
- Global rate limiter: max 30 messages/min per user (protects the bot server)
- GROQ per-user limiting is handled in groq_service.py (protects the API key)
"""

import time
from collections import defaultdict

from telegram import Update
from telegram.ext import TypeHandler, ApplicationHandlerStop

# ── Global message rate limiter ───────────────────────────────────────
# Prevents a single user from flooding the bot with any message type.
# This is independent of the GROQ per-user limit (which is stricter).

_user_requests: dict[int, list[float]] = defaultdict(list)

RATE_LIMIT_REQUESTS = 30   # max messages
RATE_LIMIT_WINDOW = 60     # per N seconds


async def rate_limit_middleware(update: Update, context) -> None:
    """
    Global rate limiting middleware: 30 requests per 60 seconds per user.
    Raises ApplicationHandlerStop to drop excess messages silently
    (after warning the user once per burst).
    """
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    now = time.monotonic()

    # Evict timestamps older than the window
    _user_requests[user_id] = [
        t for t in _user_requests[user_id] if now - t < RATE_LIMIT_WINDOW
    ]

    current_count = len(_user_requests[user_id])

    if current_count >= RATE_LIMIT_REQUESTS:
        # Warn exactly once when the limit is first hit (== RATE_LIMIT_REQUESTS)
        # Subsequent messages in the same burst are dropped silently.
        if current_count == RATE_LIMIT_REQUESTS:
            _user_requests[user_id].append(now)  # count the warning itself
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ *Slow down a little!*\n\n"
                    "You're sending messages too quickly. "
                    f"Please wait a moment before trying again. 😊",
                    parse_mode="Markdown",
                )
        raise ApplicationHandlerStop()

    _user_requests[user_id].append(now)


rate_limit_handler = TypeHandler(Update, rate_limit_middleware)
