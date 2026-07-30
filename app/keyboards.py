from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def feedback_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👍 Good", callback_data="good"),
            InlineKeyboardButton("👎 Bad", callback_data="bad")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def premium_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🌟 30 Hari - 50 Stars", callback_data="premium_30"),
            InlineKeyboardButton("🌟 90 Hari - 120 Stars", callback_data="premium_90")
        ],
        [
            InlineKeyboardButton("🌟 365 Hari - 400 Stars", callback_data="premium_365")
        ],
        [
            InlineKeyboardButton("❓ Cara Bayar", callback_data="premium_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def gender_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👨 Male", callback_data="gender_male"),
            InlineKeyboardButton("👩 Female", callback_data="gender_female")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)