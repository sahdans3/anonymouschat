from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import asyncio
import io

from app.database import (
    register_user,
    set_searching,
    join_queue,
    leave_queue,
    find_partner,
    stop_chat,
    get_partner,
    remove_user,
    is_searching,
    save_feedback,
    clear_user_status,
    get_user_status,
    check_premium,
    set_premium,
    set_gender,
    set_preferred_gender,
    get_user_gender,
    get_premium_status
)
from app.keyboards import feedback_keyboard, premium_keyboard, gender_keyboard

PARTNER_FOUND_MESSAGE = (
    "Partner found 😺\n\n"
    "/next — find a new partner\n"
    "/stop — stop this chat\n\n"
    "https://t.me/Annonymous_Chat_Bot"
)

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    try:
        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "Type your gender: *male* or *female*\n"
            "Type /search to find a partner.\n"
            "Type /premium to see premium features.\n"
            "Type /myprofile to see your profile.",
            parse_mode='Markdown'
        )
    except TelegramError as e:
        print(e)

# ================= PREMIUM COMMANDS =================

async def setpref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's preferred gender (PREMIUM ONLY)"""
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    # Check if premium
    if not check_premium(user_id):
        await update.message.reply_text(
            "🔒 *Premium Feature*\n\n"
            "Gender preference is a premium feature!\n\n"
            "To unlock this feature, please purchase premium:\n"
            "/premium - see premium options",
            parse_mode='Markdown',
            reply_markup=premium_keyboard()
        )
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Please specify your preferred gender.\n\n"
            "Usage: /setpref male\n"
            "Usage: /setpref female\n"
            "Usage: /setpref any\n\n"
            "Example: /setpref female"
        )
        return
    
    pref = args[0].lower()
    if pref not in ['male', 'female', 'any']:
        await update.message.reply_text(
            "❌ Invalid preference.\n\n"
            "Please choose: male, female, or any\n"
            "Example: /setpref female"
        )
        return
    
    if set_preferred_gender(user_id, pref):
        await update.message.reply_text(
            f"✅ Your preferred gender has been set to: *{pref}*\n\n"
            "Now when you search, you will only be matched with this gender!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to set preference. Please try again.")

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium options"""
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    is_premium, expiry = get_premium_status(user_id)
    
    status = "✅ *Active*" if is_premium else "❌ *Inactive*"
    expiry_text = f"\n📅 Expires: {expiry.strftime('%Y-%m-%d')}" if expiry and is_premium else ""
    
    premium_text = (
        f"🌟 *Premium Features*\n\n"
        f"Status: {status}{expiry_text}\n\n"
        "*Premium Benefits:*\n"
        "🎯 Filter by gender\n"
        "🔝 Priority matching\n"
        "💬 Unlimited chat history\n"
        "📊 See who liked you\n\n"
        "*Choose a plan:*"
    )
    
    await update.message.reply_text(
        premium_text,
        parse_mode='Markdown',
        reply_markup=premium_keyboard()
    )

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    gender, preferred = get_user_gender(user_id)
    is_premium, expiry = get_premium_status(user_id)
    partner = get_partner(user_id)
    
    expiry_text = f"\n📅 Expires: {expiry.strftime('%Y-%m-%d')}" if expiry and is_premium else ""
    
    profile_text = (
        f"👤 *Your Profile*\n\n"
        f"📝 User ID: `{user_id}`\n"
        f"⚧️ Gender: {gender or 'Not set'}\n"
        f"🎯 Preferred: {preferred or 'Not set'}\n"
        f"🌟 Premium: {'✅ Active' + expiry_text if is_premium else '❌ Inactive'}\n"
        f"💬 Partner: {partner if partner else 'None'}\n\n"
        "*How to use:*\n"
        "Type *male* or *female* - Set your gender\n"
        "/setpref male/female/any - Set preferred gender (premium)\n"
        "/premium - Buy premium\n"
        "/search - Find partner"
    )
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

# ================= BALANCE =================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek saldo Stars bot"""
    if update.message is None:
        return
    
    user_id = update.effective_user.id
    
    try:
        star_balance = await context.bot.get_my_star_balance()
        
        balance_text = (
            f"⭐ *Saldo Stars Bot*\n\n"
            f"Total Stars: *{star_balance}* ⭐\n\n"
            f"💡 1 Star ≈ $0.013 (nilai setelah biaya)\n"
            f"📤 Minimal withdraw: 1000 Stars\n"
            f"⏳ Masa tunggu withdraw: 21 hari\n\n"
            f"🔗 Tarik di: https://fragment.com"
        )
        
        await update.message.reply_text(balance_text, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ Balance error: {e}")
        await update.message.reply_text(
            "❌ Gagal mengambil saldo Stars.\n"
            "Pastikan bot sudah terintegrasi dengan Telegram Stars."
        )

# ================= SEARCH =================

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    clear_user_status(user_id)
    
    if get_partner(user_id):
        await update.message.reply_text("💬 You are already chatting.\nUse /next or /stop.")
        return
    
    # Check if user has set gender
    gender, _ = get_user_gender(user_id)
    if not gender:
        await update.message.reply_text(
            "⚠️ Please set your gender first!\n\n"
            "Just type: *male* or *female*\n\n"
            "This helps us match you with the right partner.",
            parse_mode='Markdown'
        )
        return
    
    set_searching(user_id, 1)
    join_queue(user_id)
    
    # 🔥 LANGSUNG cari partner setelah join queue
    partner = find_partner(user_id)
    
    if partner is None:
        await update.message.reply_text("🔍 Waiting for another user...")
        return
    
    await context.bot.send_message(chat_id=user_id, text=PARTNER_FOUND_MESSAGE)
    await context.bot.send_message(chat_id=partner, text=PARTNER_FOUND_MESSAGE)

# ================= NEXT =================

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    # Dapatkan partner lama
    old_partner = get_partner(user_id)
    
    # Stop chat
    stop_chat(user_id)
    
    # Kirim pesan ke partner lama
    if old_partner:
        try:
            await context.bot.send_message(
                chat_id=old_partner, 
                text="😞 Your partner has left the chat."
            )
        except Forbidden:
            remove_user(old_partner)
        except Exception as e:
            print(f"⚠️ Error sending to old partner: {e}")
    
    # Set searching dan join queue
    set_searching(user_id, 1)
    join_queue(user_id)
    
    # 🔥 Cari partner dengan timeout 10 detik
    partner = None
    for attempt in range(20):  # 20 x 0.5 = 10 detik
        partner = find_partner(user_id)
        if partner:
            break
        # Cek apakah user masih searching
        if not is_searching(user_id):
            break
        await asyncio.sleep(0.5)
    
    # Jika masih tidak ada partner, tetap di queue (tapi user mendapat pesan)
    if partner is None:
        await update.message.reply_text("🔍 Waiting for another user...")
        # JANGAN keluar dari queue! Tetap menunggu
        return
    
    await context.bot.send_message(
        chat_id=user_id,
        text=PARTNER_FOUND_MESSAGE
    )
    await context.bot.send_message(
        chat_id=partner,
        text=PARTNER_FOUND_MESSAGE
    )
    
    # ================= STOP =================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    partner_id = stop_chat(user_id)
    clear_user_status(user_id)
    
    if not partner_id:
        try:
            await update.message.reply_text("❌ You are not in a chat.")
        except TelegramError:
            pass
        return
    
    try:
        await context.bot.send_message(
            chat_id=partner_id, 
            text="😞 Your partner has ended the chat."
        )
    except Forbidden:
        remove_user(partner_id)
    except TelegramError as e:
        print(e)
    
    try:
        await update.message.reply_text(
            "Chat ended 😞",
            reply_markup=feedback_keyboard()
        )
    except TelegramError as e:
        print(e)

# ================= PREMIUM PAYMENT HANDLERS =================

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifikasi sebelum pembayaran"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aktifkan premium setelah pembayaran berhasil"""
    user_id = update.effective_user.id
    payload = update.message.successful_payment.payload
    days = int(payload.split('_')[1])
    
    if set_premium(user_id, days):
        await update.message.reply_text(
            f"✅ *Premium Active!*\n\n"
            f"🎉 Premium {days} hari sudah aktif!\n\n"
            "Fitur yang tersedia:\n"
            "🎯 Filter gender\n"
            "🔝 Prioritas matching\n\n"
            "Gunakan /setpref untuk atur preferensi gender!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Gagal aktivasi premium. Hubungi admin.")

# ================= REPLY HANDLER =================

async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        await update.message.reply_text("❌ You are not in a chat. Use /search to find a partner.")
        return
    
    try:
        message = update.message
        reply_to = message.reply_to_message
        
        replied_text = ""
        if reply_to:
            if reply_to.text:
                replied_text = reply_to.text
            elif reply_to.caption:
                replied_text = reply_to.caption
            elif reply_to.photo:
                replied_text = "📸 Photo"
            elif reply_to.video:
                replied_text = "🎬 Video"
            elif reply_to.document:
                replied_text = f"📄 {reply_to.document.file_name}"
            elif reply_to.sticker:
                replied_text = "🎨 Sticker"
            elif reply_to.voice:
                replied_text = "🎵 Voice"
            elif reply_to.audio:
                replied_text = "🎵 Audio"
            elif reply_to.animation:
                replied_text = "🎬 GIF"
            else:
                replied_text = "📎 Media"
        
        if replied_text:
            await context.bot.send_message(chat_id=partner_id, text=f"⬆️ {replied_text}")
        
        await context.bot.send_message(chat_id=partner_id, text=message.text)
        print("↩️ Reply sent")
        
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Your partner has left the chat. Use /search to find a new partner.")
    except Exception as e:
        print(f"❌ Reply error: {e}")
        await update.message.reply_text("❌ Failed to send reply. Please try again.")

# ================= MEDIA HANDLER =================

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        await update.message.reply_text("❌ You are not in a chat. Use /search to find a partner.")
        return
    
    try:
        message = update.message
        is_reply = message.reply_to_message is not None
        
        if is_reply:
            reply_to = message.reply_to_message
            replied_text = ""
            if reply_to.text:
                replied_text = reply_to.text
            elif reply_to.caption:
                replied_text = reply_to.caption
            elif reply_to.photo:
                replied_text = "📸 Photo"
            elif reply_to.video:
                replied_text = "🎬 Video"
            elif reply_to.document:
                replied_text = f"📄 {reply_to.document.file_name}"
            elif reply_to.sticker:
                replied_text = "🎨 Sticker"
            elif reply_to.voice:
                replied_text = "🎵 Voice"
            elif reply_to.audio:
                replied_text = "🎵 Audio"
            elif reply_to.animation:
                replied_text = "🎬 GIF"
            else:
                replied_text = "📎 Media"
            
            if replied_text:
                await context.bot.send_message(chat_id=partner_id, text=f"⬆️ {replied_text}")
        
        if message.photo:
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_photo(chat_id=partner_id, photo=io.BytesIO(file_bytes), caption=message.caption)
        elif message.video:
            video = message.video
            file = await context.bot.get_file(video.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_video(chat_id=partner_id, video=io.BytesIO(file_bytes), caption=message.caption, supports_streaming=True)
        elif message.document:
            document = message.document
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()
            mime_type = document.mime_type or ""
            is_image = mime_type.startswith('image/') or document.file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))
            if is_image:
                await context.bot.send_photo(chat_id=partner_id, photo=io.BytesIO(file_bytes), caption=message.caption)
            else:
                await context.bot.send_document(chat_id=partner_id, document=io.BytesIO(file_bytes), filename=document.file_name, caption=message.caption)
        elif message.sticker:
            await context.bot.send_sticker(chat_id=partner_id, sticker=message.sticker.file_id)
        elif message.voice:
            voice = message.voice
            file = await context.bot.get_file(voice.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_voice(chat_id=partner_id, voice=io.BytesIO(file_bytes), caption=message.caption)
        elif message.audio:
            audio = message.audio
            file = await context.bot.get_file(audio.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_audio(chat_id=partner_id, audio=io.BytesIO(file_bytes), caption=message.caption, title=audio.title, performer=audio.performer)
        elif message.animation:
            animation = message.animation
            file = await context.bot.get_file(animation.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_animation(chat_id=partner_id, animation=io.BytesIO(file_bytes), caption=message.caption)
        elif message.video_note:
            video_note = message.video_note
            file = await context.bot.get_file(video_note.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_video_note(chat_id=partner_id, video_note=io.BytesIO(file_bytes))
        else:
            await update.message.reply_text("❌ Tipe media tidak didukung.")
            
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Your partner has left the chat. Use /search to find a new partner.")
    except Exception as e:
        print(f"❌ Media error: {e}")
        await update.message.reply_text("❌ Gagal mengirim media. Silakan coba lagi.")

# ================= MESSAGE HANDLER (OTOMATIS SET GENDER) =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    # CEK APAKAH INI REPLY
    if update.message.reply_to_message is not None:
        await reply_handler(update, context)
        return
    
    # CEK APAKAH INI SET GENDER (male/female)
    text = update.message.text.lower().strip()
    if text in ['male', 'female']:
        # Cek apakah user sedang chat
        partner_id = get_partner(user_id)
        if partner_id:
            # Jika sedang chat, kirim pesan biasa
            try:
                await context.bot.send_message(chat_id=partner_id, text=update.message.text)
                print("✅ Message sent")
                return
            except Exception as e:
                print(f"❌ Send error: {e}")
                return
        
        # Jika tidak sedang chat, set gender
        register_user(user_id)
        if set_gender(user_id, text):
            await update.message.reply_text(
                f"✅ Your gender has been set to: *{text}*\n\n"
                "Now you can search for partner:\n"
                "/search - find a partner\n\n"
                "*Premium Users:*\n"
                "/setpref male/female/any - filter partner by gender",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to set gender. Please try again.")
        return
    
    # Retry get_partner (3 attempts)
    partner_id = None
    for attempt in range(3):
        partner_id = get_partner(user_id)
        if partner_id:
            break
        await asyncio.sleep(0.3)
    
    if partner_id is None:
        # Jika tidak dalam chat, cek apakah user sudah set gender
        gender, _ = get_user_gender(user_id)
        if not gender:
            await update.message.reply_text(
                "⚠️ Please set your gender first!\n\n"
                "Just type: *male* or *female*\n\n"
                "This helps us match you with the right partner.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ You are not in a chat. Use /search to find a partner.")
        return
    
    try:
        await context.bot.send_message(chat_id=partner_id, text=update.message.text)
        print("✅ Message sent")
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Your partner has left the chat. Use /search to find a new partner.")
    except Exception as e:
        print(f"❌ Send error: {e}")
        partner_check = get_partner(partner_id)
        if not partner_check:
            stop_chat(user_id)
            await update.message.reply_text("❌ Partner has left the chat. Use /search to find a new partner.")
        else:
            await update.message.reply_text("❌ Failed to send message. Please try again.")

# ================= BUTTON HANDLER =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    # Handle premium
    if data.startswith('premium_'):
        if data == 'premium_help':
            await query.edit_message_text(
                "💳 *Cara Bayar Premium*\n\n"
                "1. Pilih paket premium\n"
                "2. Bayar dengan Telegram Stars\n"
                "3. Premium aktif otomatis!\n\n"
                "*Telegram Stars* adalah mata uang Telegram.\n"
                "Kamu bisa beli Stars langsung dari Telegram.",
                parse_mode='Markdown',
                reply_markup=premium_keyboard()
            )
            return
        
        days = int(data.split('_')[1])
        
        # Kirim invoice dengan Telegram Stars
        await context.bot.send_invoice(
            chat_id=user_id,
            title=f"Premium {days} Hari",
            description=f"Aktifkan premium selama {days} hari!\n\nFitur:\n✅ Filter gender\n✅ Prioritas matching",
            payload=f"premium_{days}",
            provider_token="",
            currency="XTR",
            prices=[{"label": f"{days} Hari Premium", "amount": days * 2}],
            start_parameter="premium_subscription"
        )
        return
    
    # Handle feedback
    partner_id = get_partner(user_id)
    if partner_id:
        try:
            save_feedback(from_user=user_id, to_user=partner_id, feedback=data)
        except Exception as e:
            print(e)
    
    await query.edit_message_text("✅ Thank you for your feedback!")

# ================= ERROR HANDLER =================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("=" * 50)
    print(f"Update: {update}")
    print(f"Error: {context.error}")
    print("=" * 50)
    
    if update and update.effective_user:
        user_id = update.effective_user.id
        try:
            clear_user_status(user_id)
        except Exception as e:
            print(f"❌ Error clearing status: {e}")
    
    if update and update.effective_user:
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="❌ Maaf, terjadi kesalahan. Silakan coba /search lagi."
            )
        except Forbidden:
            print(f"⚠️ User {update.effective_user.id} blocked the bot")
        except:
            pass