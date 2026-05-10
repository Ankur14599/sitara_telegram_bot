"""
Order-related inline keyboards.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def order_actions_keyboard(order_number: str) -> InlineKeyboardMarkup:
    """Inline keyboard with actions for a specific order."""
    keyboard = [
        [
            InlineKeyboardButton("👁 View", callback_data=f"order:view:{order_number}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"order:edit:{order_number}"),
        ],
        [
            InlineKeyboardButton("✅ Complete", callback_data=f"order:complete:{order_number}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"order:cancel:{order_number}"),
        ],
        [
            InlineKeyboardButton("💰 Record Payment", callback_data=f"payment:record:{order_number}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def order_confirm_keyboard(order_number: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for order completion/cancellation."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, confirm", callback_data=f"order:confirm_action:{order_number}"),
            InlineKeyboardButton("❌ No, go back", callback_data=f"order:cancel_action:{order_number}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def orders_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination keyboard for order list."""
    buttons = []

    if current_page > 1:
        buttons.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"page:orders:{current_page - 1}")
        )
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"page:orders:{current_page + 1}")
        )

    keyboard = [buttons] if buttons else []
    return InlineKeyboardMarkup(keyboard)
