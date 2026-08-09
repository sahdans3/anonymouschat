from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    PreCheckoutQueryHandler
)
from flask import Flask
from threading import Thread
import os
import time

from app.config import BOT_TOKEN
from app.database import init_db, start_keep_alive
from app.handlers import (
    start,
    search,
    next_chat,
    stop,
    button_handler,
    message_handler,
    media_handler,
    error_handler,
    premium,
    setpref,
    myprofile,
    balance,
    pre_checkout_handler,
    successful_payment_handler,
    referral,
    referral_stats,
    gender_selection,
    admin_premium,
    cek_premium,
    report_bug
)

flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "🤖 Bot is running!", 200

def run_health_server():
    port = int(os.environ.get('PORT', 8080))
    try:
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"⚠️ Health server error: {e}")

def run_bot():
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN tidak ditemukan")
        return

    init_db()
    start_keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("next", next_chat))
    app.add_handler(CommandHandler("stop", stop))
    
    # Premium handlers
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("setpref", setpref))
    app.add_handler(CommandHandler("myprofile", myprofile))
    app.add_handler(CommandHandler("balance", balance))
    
    # Referral handlers
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("referstats", referral_stats))
    
    # Gender handler
    app.add_handler(CommandHandler("gender", gender_selection))
    
    # Admin handlers
    app.add_handler(CommandHandler("setpremium", admin_premium))
    app.add_handler(CommandHandler("cekpremium", cek_premium))
    app.add_handler(CommandHandler("report_bug", report_bug))

    # Payment handlers
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # Button handler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Media handlers
    app.add_handler(MessageHandler(filters.PHOTO, media_handler))
    app.add_handler(MessageHandler(filters.VIDEO, media_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, media_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, media_handler))
    app.add_handler(MessageHandler(filters.VOICE, media_handler))
    app.add_handler(MessageHandler(filters.AUDIO, media_handler))
    app.add_handler(MessageHandler(filters.ANIMATION, media_handler))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, media_handler))
    
    # Text message handler
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    # Error Handler
    app.add_error_handler(error_handler)

    print("🤖 Bot sedang berjalan...")
    app.run_polling()

if __name__ == "__main__":
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    time.sleep(2)
    run_bot()