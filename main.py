from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
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
    error_handler
)

# Flask app untuk health check
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
    """Run the bot in a separate thread"""
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN tidak ditemukan")
        return

    # Inisialisasi database
    init_db()
    
    # Start keep-alive thread
    start_keep_alive()

    # Buat aplikasi
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("next", next_chat))
    app.add_handler(CommandHandler("stop", stop))

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
    # Jalankan Flask di thread terpisah
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Tunggu sebentar agar Flask siap
    time.sleep(2)
    
    # Jalankan bot di thread utama
    run_bot()