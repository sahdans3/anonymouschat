from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import asyncio
import io
from datetime import datetime

from app.database import (
    register_user,
    set_searching,
    join_queue,
    find_partner,
    stop_chat,
    get_partner,
    remove_user,
    save_feedback,
    clear_user_status,
    check_premium,
    set_premium,
    set_gender,
    set_preferred_gender,
    get_user_gender,
    get_premium_status,
    is_searching
)
from app.keyboards import feedback_keyboard, premium_keyboard

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
            "Type /premium to see premium features.",
            parse_mode='Markdown'
        )
    except TelegramError as e:
        print(e)

# ================= PREMIUM =================

async def setpref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    if not check_premium(user_id):
        await update.message.reply_text(
            "🔒 *Premium Feature*\n\n"
            "Gender preference is a premium feature!\n\n"
            "/premium - see premium options",
            parse_mode='Markdown',
            reply_markup=premium_keyboard()
        )
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Usage: /setpref male\n"
            "Usage: /setpref female\n"
            "Usage: /setpref any"
        )
        return
    
    pref = args[0].lower()
    if pref not in ['male', 'female', 'any']:
        await update.message.reply_text("❌ Choose: male, female, or any")
        return
    
    if set_preferred_gender(user_id, pref):
        await update.message.reply_text(f"✅ Preferred gender: *{pref}*", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to set preference.")

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    is_premium, expiry = get_premium_status(user_id)
    status = "✅ *Active*" if is_premium else "❌ *Inactive*"
    expiry_text = f"\n📅 Expires: {expiry.strftime('%Y-%m-%d')}" if expiry and is_premium else ""
    
    await update.message.reply_text(
        f"🌟 *Premium*\n\nStatus: {status}{expiry_text}\n\n"
        "🎯 Filter gender\n"
        "🔝 Priority matching\n\n"
        "Choose plan:",
        parse_mode='Markdown',
        reply_markup=premium_keyboard()
    )

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    gender, preferred = get_user_gender(user_id)
    is_premium, expiry = get_premium_status(user_id)
    partner = get_partner(user_id)
    
    await update.message.reply_text(
        f"👤 *Profile*\n\n"
        f"Gender: {gender or 'Not set'}\n"
        f"Preferred: {preferred or 'Not set'}\n"
        f"Premium: {'✅ Active' if is_premium else '❌ Inactive'}\n"
        f"Partner: {partner if partner else 'None'}",
        parse_mode='Markdown'
    )

# ================= BALANCE =================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    try:
        star_balance = await context.bot.get_my_star_balance()
        await update.message.reply_text(
            f"⭐ *Saldo Stars Bot*\n\n"
            f"Total: *{star_balance}* ⭐\n\n"
            f"💡 1 Star ≈ $0.013\n"
            f"📤 Minimal withdraw: 1000 Stars\n"
            f"🔗 Tarik di: https://fragment.com",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Balance error: {e}")
        await update.message.reply_text("❌ Gagal mengambil saldo Stars.")

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
    
    gender, _ = get_user_gender(user_id)
    if not gender:
        await update.message.reply_text(
            "⚠️ Set your gender first!\n\n"
            "Type: *male* or *female*",
            parse_mode='Markdown'
        )
        return
    
    # 🔥 JOIN QUEUE DAN LANGSUNG CARI PARTNER
    set_searching(user_id, 1)
    join_queue(user_id)
    
    # 🔥 LANGSUNG cari partner
    partner = find_partner(user_id)
    
    if partner:
        await context.bot.send_message(chat_id=user_id, text=PARTNER_FOUND_MESSAGE)
        await context.bot.send_message(chat_id=partner, text=PARTNER_FOUND_MESSAGE)
    else:
        await update.message.reply_text("🔍 Waiting for another user...")

# ================= NEXT =================

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    old_partner = get_partner(user_id)
    stop_chat(user_id)
    
    if old_partner:
        try:
            await context.bot.send_message(
                chat_id=old_partner, 
                text="😞 Your partner has left the chat."
            )
        except Forbidden:
            remove_user(old_partner)
        except Exception as e:
            print(f"⚠️ Error: {e}")
    
    # 🔥 JOIN QUEUE DAN LANGSUNG CARI PARTNER
    set_searching(user_id, 1)
    join_queue(user_id)
    
    # 🔥 LANGSUNG cari partner
    partner = find_partner(user_id)
    
    if partner:
        await context.bot.send_message(chat_id=user_id, text=PARTNER_FOUND_MESSAGE)
        await context.bot.send_message(chat_id=partner, text=PARTNER_FOUND_MESSAGE)
    else:
        await update.message.reply_text("🔍 Waiting for another user...")

# ================= STOP =================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    partner_id = stop_chat(user_id)
    clear_user_status(user_id)
    
    if not partner_id:
        await update.message.reply_text("❌ You are not in a chat.")
        return
    
    try:
        await context.bot.send_message(chat_id=partner_id, text="😞 Your partner has ended the chat.")
    except Forbidden:
        remove_user(partner_id)
    except Exception as e:
        print(e)
    
    await update.message.reply_text("Chat ended 😞", reply_markup=feedback_keyboard())

# ================= PAYMENT =================

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.payload
    days = int(payload.split('_')[1])
    
    if set_premium(user_id, days):
        await update.message.reply_text(
            f"✅ *Premium Active!* 🎉\n\n"
            f"Premium {days} hari aktif!\n"
            "🎯 Filter gender unlocked!\n"
            "Use /setpref to set preferred gender.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Gagal aktivasi premium.")

# ================= REPLY =================

async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        await update.message.reply_text("❌ You are not in a chat. Use /search.")
        return
    
    try:
        message = update.message
        reply_to = message.reply_to_message
        
        replied_text = ""
        if reply_to:
            if reply_to.text:
                replied_text = reply_to.text
            elif reply_to.photo:
                replied_text = "📸 Photo"
            elif reply_to.video:
                replied_text = "🎬 Video"
            elif reply_to.sticker:
                replied_text = "🎨 Sticker"
            else:
                replied_text = "📎 Media"
        
        if replied_text:
            await context.bot.send_message(chat_id=partner_id, text=f"⬆️ {replied_text}")
        
        await context.bot.send_message(chat_id=partner_id, text=message.text)
        
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Partner left. Use /search.")
    except Exception as e:
        print(f"❌ Reply error: {e}")
        await update.message.reply_text("❌ Failed to send reply.")

# ================= MEDIA =================

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        await update.message.reply_text("❌ You are not in a chat. Use /search.")
        return
    
    try:
        message = update.message
        is_reply = message.reply_to_message is not None
        
        if is_reply:
            reply_to = message.reply_to_message
            replied_text = ""
            if reply_to.text:
                replied_text = reply_to.text
            elif reply_to.photo:
                replied_text = "📸 Photo"
            elif reply_to.video:
                replied_text = "🎬 Video"
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
            await context.bot.send_video(chat_id=partner_id, video=io.BytesIO(file_bytes), caption=message.caption)
        elif message.sticker:
            await context.bot.send_sticker(chat_id=partner_id, sticker=message.sticker.file_id)
        elif message.voice:
            voice = message.voice
            file = await context.bot.get_file(voice.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_voice(chat_id=partner_id, voice=io.BytesIO(file_bytes))
        elif message.animation:
            animation = message.animation
            file = await context.bot.get_file(animation.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_animation(chat_id=partner_id, animation=io.BytesIO(file_bytes))
            
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Partner left. Use /search.")
    except Exception as e:
        print(f"❌ Media error: {e}")
        await update.message.reply_text("❌ Failed to send media.")

# ================= MESSAGE =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    if update.message.reply_to_message is not None:
        await reply_handler(update, context)
        return
    
    text = update.message.text.lower().strip()
    if text in ['male', 'female']:
        partner_id = get_partner(user_id)
        if partner_id:
            try:
                await context.bot.send_message(chat_id=partner_id, text=update.message.text)
                return
            except Exception as e:
                print(f"❌ Send error: {e}")
                return
        
        register_user(user_id)
        if set_gender(user_id, text):
            await update.message.reply_text(
                f"✅ Gender set to: *{text}*\n\n"
                "Now type /search to find a partner.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to set gender.")
        return
    
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        gender, _ = get_user_gender(user_id)
        if not gender:
            await update.message.reply_text(
                "⚠️ Set your gender first!\n\nType: *male* or *female*",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Not in a chat. Use /search.")
        return
    
    try:
        await context.bot.send_message(chat_id=partner_id, text=update.message.text)
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Partner left. Use /search.")
    except Exception as e:
        print(f"❌ Send error: {e}")

# ================= BUTTON =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith('premium_'):
        if data == 'premium_help':
            await query.edit_message_text(
                "💳 *Cara Bayar*\n\n"
                "1. Pilih paket\n"
                "2. Bayar dengan Telegram Stars\n"
                "3. Premium aktif!",
                parse_mode='Markdown',
                reply_markup=premium_keyboard()
            )
            return
        
        days = int(data.split('_')[1])
        
        await context.bot.send_invoice(
            chat_id=user_id,
            title=f"Premium {days} Hari",
            description=f"Premium {days} hari!",
            payload=f"premium_{days}",
            provider_token="",
            currency="XTR",
            prices=[{"label": f"{days} Hari", "amount": days * 2}],
            start_parameter="premium_subscription"
        )
        return
    
    partner_id = get_partner(user_id)
    if partner_id:
        try:
            save_feedback(from_user=user_id, to_user=partner_id, feedback=data)
        except Exception as e:
            print(e)
    
    await query.edit_message_text("✅ Thank you for your feedback!")

# ================= ERROR =================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("=" * 50)
    print(f"Error: {context.error}")
    print("=" * 50)
    
    if update and update.effective_user:
        user_id = update.effective_user.id
        try:
            clear_user_status(user_id)
        except Exception as e:
            print(f"❌ Error clearing status: {e}")