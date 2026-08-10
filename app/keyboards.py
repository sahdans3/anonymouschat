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
            InlineKeyboardButton("🌟 30 Hari - 60 ⭐", callback_data="premium_30"),
            InlineKeyboardButton("🌟 90 Hari - 180 ⭐", callback_data="premium_90")
        ],
        [
            InlineKeyboardButton("🌟 365 Hari - 730 ⭐", callback_data="premium_365")
        ],
        [
            InlineKeyboardButton("💳 Cara Bayar", callback_data="premium_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def gender_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👨 Male", callback_data="gender_male"),
            InlineKeyboardButton("👩 Female", callback_data="gender_female")
        ],
        [
            InlineKeyboardButton("🗑️ Hapus Gender", callback_data="gender_delete")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def filter_gender_keyboard_with_current(current_filter):
    male_icon = "✅ " if current_filter == "male" else ""
    female_icon = "✅ " if current_filter == "female" else ""
    any_icon = "✅ " if current_filter == "any" or current_filter is None else ""
    
    keyboard = [
        [
            InlineKeyboardButton(f"{male_icon}👨 Male", callback_data="filter_male"),
            InlineKeyboardButton(f"{female_icon}👩 Female", callback_data="filter_female")
        ],
        [
            InlineKeyboardButton(f"{any_icon}🌐 Any", callback_data="filter_any")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)