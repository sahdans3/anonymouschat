from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import asyncio
import io
import time
import random

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
            "Type /search to find a partner.\n"
            "Type /premium to see premium features.\n"
            "Type /myprofile to see your profile."
        )
    except TelegramError as e:
        print(e)

# ================= PREMIUM COMMANDS =================

# ================= SET GENDER (OTOMATIS) =================

async def setgender_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto detect gender from text message"""
    if update.message is None:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.lower().strip()
    
    # Cek apakah teks adalah male atau female
    if text in ['male', 'female']:
        register_user(user_id)
        
        # Cek apakah user sedang dalam chat
        if get_partner(user_id):
            await update.message.reply_text(
                "❌ You are in a chat. Use /stop first to change gender."
            )
            return
        
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
    
    await update.message.reply_text(
        f"🌟 *Premium Features*\n\n"
        f"Status: {status}{expiry_text}\n\n"
        "*Premium Benefits:*\n"
        "🎯 Filter by gender\n"
        "🔝 Priority matching\n"
        "💬 Unlimited chat history\n"
        "📊 See who liked you\n\n"
        "*Choose a plan:*",
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
        "*Commands:*\n"
        "/setgender male/female - Set your gender\n"
        "/setpref male/female/any - Set preferred gender (premium)\n"
        "/premium - Buy premium\n"
        "/search - Find partner"
    )
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

# ================= BALANCE (CEK SALDO STARS) =================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek saldo Stars bot"""
    if update.message is None:
        return
    
    user_id = update.effective_user.id
    
    try:
        # Panggil API Telegram untuk cek saldo Stars
        star_balance = await context.bot.get_my_star_balance()
        
        await update.message.reply_text(
            f"⭐ *Saldo Stars Bot*\n\n"
            f"Total Stars: *{star_balance}* ⭐\n\n"
            f"💡 1 Star ≈ $0.013 (nilai setelah biaya)\n"
            f"📤 Minimal withdraw: 1000 Stars\n"
            f"⏳ Masa tunggu withdraw: 21 hari\n\n"
            f"🔗 Tarik di: https://fragment.com",
            parse_mode='Markdown'
        )
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
            "Use /setgender male or /setgender female\n\n"
            "This helps us match you with the right partner."
        )
        return
    
    # SET SEARCHING LANGSUNG
    set_searching(user_id, 1)
    
    # Coba cari partner INSTAN
    partner = find_partner(user_id)
    
    # Jika tidak ada partner, baru masuk queue
    if partner is None:
        join_queue(user_id)
        
        # Coba cari partner lagi (dengan retry cepat)
        for attempt in range(5):
            partner = find_partner(user_id)
            if partner:
                break
            await asyncio.sleep(0.2)
    
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
    clear_user_status(user_id)
    
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
    
    # SET SEARCHING LANGSUNG (tanpa delay)
    set_searching(user_id, 1)
    
    # Coba cari partner INSTAN (tanpa queue)
    partner = find_partner(user_id)
    
    # Jika tidak ada partner, baru masuk queue
    if partner is None:
        join_queue(user_id)
        
        # Coba cari partner lagi (dengan retry cepat)
        for attempt in range(5):
            partner = find_partner(user_id)
            if partner:
                break
            await asyncio.sleep(0.2)  # delay sangat cepat 0.2 detik
    
    if partner is None:
        await update.message.reply_text("🔍 Waiting for another user...")
        return
    
    # Kirim pesan ke kedua user
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

# ================= MESSAGE HANDLER =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    # CEK APAKAH INI REPLY
    if update.message.reply_to_message is not None:
        await reply_handler(update, context)
        return
    
    # CEK APAKAH INI PERINTAH SET GENDER (male/female)
    text = update.message.text.lower().strip()
    if text in ['male', 'female']:
        # Cek apakah user sudah register dan punya partner
        partner_id = get_partner(user_id)
        if partner_id:
            # Jika sedang chat, kirim pesan biasa (bukan set gender)
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
        # Jika tidak dalam chat dan tidak ada gender, minta set gender
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
    
    try:
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        
        # Handle premium callback
        if data.startswith('premium_'):
            if data == 'premium_help':
                await query.edit_message_text(
                    "💳 *How to Buy Premium*\n\n"
                    "1. Choose your plan\n"
                    "2. Pay with Telegram Stars\n"
                    "3. Premium activated instantly!\n\n"
                    "*Telegram Stars* are Telegram's in-app currency.\n"
                    "You can buy them directly from Telegram.",
                    parse_mode='Markdown',
                    reply_markup=premium_keyboard()
                )
                return
            
            days = int(data.split('_')[1])
            
            await query.edit_message_text(
                f"⏳ Processing your premium purchase for {days} days...\n\n"
                "Please wait..."
            )
            
            time.sleep(2)
            
            if set_premium(user_id, days):
                await query.edit_message_text(
                    f"✅ *Premium Activated!*\n\n"
                    f"🎉 You now have premium for {days} days!\n\n"
                    "*Features unlocked:*\n"
                    "🎯 Gender filtering\n"
                    "🔝 Priority matching\n"
                    "💬 Unlimited chat history\n\n"
                    "Use /setpref to set your preferred gender!",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ Failed to activate premium. Please try again.",
                    reply_markup=premium_keyboard()
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
        
    except BadRequest:
        pass
    except TelegramError as e:
        print(e)

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