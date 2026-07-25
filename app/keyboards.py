from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def feedback_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👍 Good", callback_data="good"),
            InlineKeyboardButton("👎 Bad", callback_data="bad")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)