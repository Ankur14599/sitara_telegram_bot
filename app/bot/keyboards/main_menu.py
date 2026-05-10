"""
Main menu inline keyboard for quick actions.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📦 Orders", callback_data="menu:orders"),
            InlineKeyboardButton("📊 Inventory", callback_data="menu:inventory"),
        ],
        [
            InlineKeyboardButton("👥 Customers", callback_data="menu:customers"),
            InlineKeyboardButton("💰 Payments", callback_data="menu:payments"),
        ],
        [
            InlineKeyboardButton("📋 Summary", callback_data="menu:summary"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
