from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest, TelegramError
import asyncio
import io
import traceback
from datetime import datetime, timedelta

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
    is_searching,
    start_chat_session,
    end_chat_session,
    get_chat_report,
    save_waiting_message,
    delete_waiting_message,
    increment_partner_count,
    get_partner_count,
    reset_partner_count,
    get_last_partner_reset,
    check_daily_limit,
    create_referral_code,
    get_referral_code,
    use_referral_code,
    get_referral_stats,
    is_referred,
    get_referrer
)
from app.keyboards import feedback_keyboard, premium_keyboard, gender_keyboard

PARTNER_FOUND_MESSAGE = (
    "Partner found 😺\n\n"
    "/next — find a new partner\n"
    "/stop — stop this chat\n\n"
    "https://t.me/Annonymous_Chat_Bot"
)

FREE_USER_LIMIT = 6
COOLDOWN_HOURS = 19

# ================= SEND CHAT REPORT =================

async def send_chat_report_to_user(context, user_id, partner_id):
    chat_id = end_chat_session(user_id)
    if chat_id:
        report = get_chat_report(chat_id)
        if report:
            duration = report['duration']
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
            
            report_text = (
                f"📊 *Chat Report*\n\n"
                f"👤 You: `{user_id}`\n"
                f"👤 Partner: `{partner_id}`\n"
                f"⏱️ Duration: {duration_str}\n\n"
                f"💬 How was your chat?"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=report_text,
                    parse_mode='Markdown',
                    reply_markup=feedback_keyboard()
                )
            except Exception as e:
                print(f"❌ Send report to user1 error: {e}")
            
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=report_text,
                    parse_mode='Markdown',
                    reply_markup=feedback_keyboard()
                )
            except Exception as e:
                print(f"❌ Send report to user2 error: {e}")

# ================= GENDER SELECTION =================

async def gender_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    partner_id = get_partner(user_id)
    if partner_id:
        await update.message.reply_text(
            "❌ You are in a chat. Please /stop first to change gender."
        )
        return
    
    await update.message.reply_text(
        "👤 *Select your gender:*\n\n"
        "Choose your gender to help us match you with the right partner.",
        parse_mode='Markdown',
        reply_markup=gender_keyboard()
    )

async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "gender_male":
        gender = "male"
    elif data == "gender_female":
        gender = "female"
    else:
        return
    
    if set_gender(user_id, gender):
        await query.edit_message_text(
            f"✅ Your gender has been set to: *{gender}*\n\n"
            "Now type /search to find a partner.\n\n"
            "*Premium Users:*\n"
            "Use /setpref male/female/any to filter partners by gender.",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Failed to set gender. Please try again.")

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    if context.args:
        code = context.args[0].upper().strip()
        if not is_referred(user_id):
            success, result = use_referral_code(user_id, code)
            if success:
                referrer_id = result
                await update.message.reply_text(
                    f"✅ *Referral link activated!* 🎉\n\n"
                    f"You joined using a referral link.\n"
                    f"Your referrer has been rewarded!\n\n"
                    f"Thank you for joining! 🙌",
                    parse_mode='Markdown'
                )
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 *Someone joined using your referral link!*\n\n"
                             f"Your referral count has increased!\n"
                             f"Check /referral for your stats.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"⚠️ Error sending referral notification: {e}")
    
    is_premium = check_premium(user_id)
    premium_tag = "⭐ *Premium*" if is_premium else ""
    
    gender, _ = get_user_gender(user_id)
    
    try:
        if gender:
            await update.message.reply_text(
                f"👋 Welcome back!\n\n"
                f"{premium_tag}\n\n"
                f"⚧️ Your gender: *{gender}*\n\n"
                "Type /search to find a partner.\n"
                "Type /premium to see premium features.\n"
                "Type /myprofile to see your profile.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"👋 Welcome!\n\n"
                f"{premium_tag}\n\n"
                "Please select your gender to continue:",
                parse_mode='Markdown',
                reply_markup=gender_keyboard()
            )
    except TelegramError as e:
        print(e)

# ================= REFERRAL COMMANDS =================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    code = create_referral_code(user_id)
    if not code:
        await update.message.reply_text("❌ Failed to create referral code.")
        return
    
    count, referred = get_referral_stats(user_id)
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={code}"
    reward_chats = count * 5
    
    text = (
        f"🎁 *Referral Program*\n\n"
        f"📤 *Share this link:*\n"
        f"`{referral_link}`\n\n"
        f"📊 *Your Stats:*\n"
        f"👤 Referred: {count} people\n"
        f"🎯 Extra chats: +{reward_chats}\n\n"
        f"💡 Share link → friends join → you get rewards!"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📤 Share Link", url=referral_link),
            InlineKeyboardButton("📋 Copy Text", callback_data="copy_referral")
        ],
        [
            InlineKeyboardButton("📊 Referral Stats", callback_data="referral_stats")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    code = get_referral_code(user_id)
    count, referred = get_referral_stats(user_id)
    referred_by = get_referrer(user_id)
    
    text = (
        f"📊 *Referral Details*\n\n"
        f"Your code: `{code or 'Not set'}`\n"
        f"Total referred: {count}\n"
        f"Extra chats: +{count * 5}\n"
    )
    
    if referred_by:
        text += f"\n👤 You were referred by: `{referred_by}`\n"
    
    if referred:
        text += f"\n📋 Last referrals:\n"
        for uid, created_at in referred[:5]:
            text += f"• User `{uid}` joined {created_at.strftime('%d/%m')}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    
    await query.answer()
    user_id = query.from_user.id
    code = get_referral_code(user_id)
    if not code:
        code = create_referral_code(user_id)
    
    count, referred = get_referral_stats(user_id)
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={code}"
    reward_chats = count * 5
    
    text = (
        f"🎁 *Referral Program*\n\n"
        f"📤 *Share this link:*\n"
        f"`{referral_link}`\n\n"
        f"📊 *Stats:*\n"
        f"👤 Referred: {count} people\n"
        f"🎯 Extra chats: +{reward_chats}\n\n"
        f"💡 Share link → friends join → you get rewards!"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📤 Share", url=referral_link),
            InlineKeyboardButton("📋 Copy", callback_data="copy_referral")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="referral_stats")
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= PREMIUM COMMANDS =================

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
        "🔝 Priority matching\n"
        "♾️ Unlimited partners\n"
        "⏳ No daily limit\n\n"
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
    partner_count = get_partner_count(user_id)
    last_reset = get_last_partner_reset(user_id)
    
    premium_tag = "⭐ *Premium*" if is_premium else "❌ Free"
    expiry_text = f"\n📅 Expires: {expiry.strftime('%Y-%m-%d')}" if expiry and is_premium else ""
    
    limit_info = ""
    if not is_premium:
        remaining = FREE_USER_LIMIT - partner_count
        limit_info = f"\n📊 Today: {partner_count}/{FREE_USER_LIMIT}"
        if remaining <= 5:
            limit_info += f" ⚠️ {remaining} remaining!"
        
        if partner_count >= FREE_USER_LIMIT and last_reset:
            reset_time = last_reset + timedelta(hours=COOLDOWN_HOURS)
            now = datetime.now()
            if reset_time > now:
                remaining_time = reset_time - now
                hours = remaining_time.total_seconds() // 3600
                minutes = (remaining_time.total_seconds() % 3600) // 60
                limit_info += f"\n⏳ Reset in: {int(hours)}h {int(minutes)}m"
    else:
        limit_info = f"\n📊 Partners: {partner_count} ♾️ (Unlimited)"
    
    await update.message.reply_text(
        f"👤 *Profile*\n\n"
        f"{premium_tag}\n\n"
        f"Gender: {gender or 'Not set'}\n"
        f"Preferred: {preferred or 'Not set'}\n"
        f"Premium: {'✅ Active' + expiry_text if is_premium else '❌ Inactive'}"
        f"{limit_info}\n"
        f"Partner: {partner if partner else 'None'}",
        parse_mode='Markdown'
    )

# ================= BALANCE =================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    
    user_id = update.effective_user.id
    
    try:
        star_balance = await context.bot.get_my_star_balance()
        await update.message.reply_text(
            f"⭐ *Saldo Stars Bot*\n\n"
            f"Total Stars: *{star_balance}* ⭐\n\n"
            f"💡 1 Star ≈ $0.013\n"
            f"📤 Minimal withdraw: 1000 Stars\n"
            f"🔗 Tarik di: https://fragment.com",
            parse_mode='Markdown'
        )
    except AttributeError as e:
        print(f"❌ AttributeError: {e}")
        await update.message.reply_text(
            "❌ Bot ini menggunakan versi lama.\n"
            "Mohon hubungi admin untuk update."
        )
    except Exception as e:
        print(f"❌ Balance error: {e}")
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Gagal mengambil saldo Stars.\n"
            f"Error: {str(e)[:100]}"
        )

# ================= DELETE WAITING MESSAGE =================

async def delete_waiting_message_from_db(context, user_id):
    waiting_info = delete_waiting_message(user_id)
    if waiting_info:
        chat_id, message_id = waiting_info
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
            return True
        except Exception as e:
            print(f"⚠️ Error deleting waiting message: {e}")
    return False

# ================= SEARCH =================

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    can_search, count, remaining_hours = check_daily_limit(user_id)
    if not can_search:
        hours = remaining_hours
        await update.message.reply_text(
            f"🚫 *Daily Limit Reached*\n\n"
            f"You have reached the maximum of {FREE_USER_LIMIT} free partners today.\n\n"
            f"⏳ Please wait *{hours} hours* before searching again.\n\n"
            f"Or upgrade to Premium for unlimited access:\n"
            f"/premium - see premium options",
            parse_mode='Markdown',
            reply_markup=premium_keyboard()
        )
        return
    
    partner = get_partner(user_id)
    if partner:
        await send_chat_report_to_user(context, user_id, partner)
        stop_chat(user_id)
        clear_user_status(user_id)
        await update.message.reply_text("💬 You left your previous chat.\nSearching for new partner...")
    
    clear_user_status(user_id)
    
    gender, _ = get_user_gender(user_id)
    if not gender:
        await update.message.reply_text(
            "⚠️ Please select your gender first!",
            parse_mode='Markdown',
            reply_markup=gender_keyboard()
        )
        return
    
    if not check_premium(user_id):
        partner_count = get_partner_count(user_id)
        remaining = FREE_USER_LIMIT - partner_count
        if remaining <= 5 and remaining > 0:
            await update.message.reply_text(
                f"⚠️ *Free User Limit*\n\n"
                f"You have {remaining} free partner searches remaining today.\n"
                f"Type /premium to upgrade for unlimited access.",
                parse_mode='Markdown'
            )
    
    set_searching(user_id, 1)
    join_queue(user_id)
    
    partner = find_partner(user_id)
    
    if partner:
        start_chat_session(user_id, partner)
        await delete_waiting_message_from_db(context, partner)
        increment_partner_count(user_id)
        increment_partner_count(partner)
        
        await context.bot.send_message(chat_id=user_id, text=PARTNER_FOUND_MESSAGE)
        await context.bot.send_message(chat_id=partner, text=PARTNER_FOUND_MESSAGE)
    else:
        waiting_msg = await update.message.reply_text("🔍 Waiting for another user...")
        save_waiting_message(user_id, waiting_msg.chat_id, waiting_msg.message_id)

# ================= NEXT =================

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    register_user(user_id)
    
    can_search, count, remaining_hours = check_daily_limit(user_id)
    if not can_search:
        hours = remaining_hours
        await update.message.reply_text(
            f"🚫 *Daily Limit Reached*\n\n"
            f"You have reached the maximum of {FREE_USER_LIMIT} free partners today.\n\n"
            f"⏳ Please wait *{hours} hours* before searching again.\n\n"
            f"Or upgrade to Premium for unlimited access:\n"
            f"/premium - see premium options",
            parse_mode='Markdown',
            reply_markup=premium_keyboard()
        )
        return
    
    old_partner = get_partner(user_id)
    
    if old_partner:
        await send_chat_report_to_user(context, user_id, old_partner)
        
        try:
            await context.bot.send_message(
                chat_id=old_partner, 
                text="😞 Your partner has left the chat."
            )
        except Forbidden:
            remove_user(old_partner)
        except Exception as e:
            print(f"⚠️ Error: {e}")
    
    stop_chat(user_id)
    clear_user_status(user_id)
    
    set_searching(user_id, 1)
    join_queue(user_id)
    
    partner = find_partner(user_id)
    
    if partner:
        start_chat_session(user_id, partner)
        await delete_waiting_message_from_db(context, user_id)
        await delete_waiting_message_from_db(context, partner)
        increment_partner_count(user_id)
        increment_partner_count(partner)
        
        await context.bot.send_message(chat_id=user_id, text=PARTNER_FOUND_MESSAGE)
        await context.bot.send_message(chat_id=partner, text=PARTNER_FOUND_MESSAGE)
    else:
        waiting_msg = await update.message.reply_text("🔍 Waiting for another user...")
        save_waiting_message(user_id, waiting_msg.chat_id, waiting_msg.message_id)

# ================= STOP =================

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    await delete_waiting_message_from_db(context, user_id)
    
    partner_id = get_partner(user_id)
    
    if partner_id:
        await send_chat_report_to_user(context, user_id, partner_id)
        
        try:
            await context.bot.send_message(
                chat_id=partner_id, 
                text="😞 Your partner has ended the chat."
            )
        except Forbidden:
            remove_user(partner_id)
        except Exception as e:
            print(e)
    
    stop_chat(user_id)
    clear_user_status(user_id)
    
    if not partner_id:
        await update.message.reply_text("❌ You are not in a chat.")
        return
    
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
            "♾️ Unlimited partners!\n"
            "⏳ No daily limit!\n"
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
        
        is_premium = check_premium(user_id)
        
        if replied_text:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"⬆️ {replied_text}"
            )
        
        if is_premium:
            await context.bot.send_message(
                chat_id=partner_id,
                text="⭐ *Premium*",
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                chat_id=partner_id,
                text=message.text
            )
        else:
            await context.bot.send_message(
                chat_id=partner_id,
                text=message.text
            )
        
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
        
        is_premium = check_premium(user_id)
        
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
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"⬆️ {replied_text}"
                )
        
        caption = message.caption or ""
        
        if is_premium:
            await context.bot.send_message(
                chat_id=partner_id,
                text="⭐ *Premium*",
                parse_mode='Markdown'
            )
        
        if message.photo:
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_photo(
                chat_id=partner_id,
                photo=io.BytesIO(file_bytes),
                caption=caption
            )
        elif message.video:
            video = message.video
            file = await context.bot.get_file(video.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_video(
                chat_id=partner_id,
                video=io.BytesIO(file_bytes),
                caption=caption
            )
        elif message.sticker:
            await context.bot.send_sticker(
                chat_id=partner_id,
                sticker=message.sticker.file_id
            )
        elif message.voice:
            voice = message.voice
            file = await context.bot.get_file(voice.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_voice(
                chat_id=partner_id,
                voice=io.BytesIO(file_bytes),
                caption=caption
            )
        elif message.animation:
            animation = message.animation
            file = await context.bot.get_file(animation.file_id)
            file_bytes = await file.download_as_bytearray()
            await context.bot.send_animation(
                chat_id=partner_id,
                animation=io.BytesIO(file_bytes),
                caption=caption
            )
            
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Partner left. Use /search.")
    except Exception as e:
        print(f"❌ Media error: {e}")
        await update.message.reply_text("❌ Failed to send media.")

# ================= MESSAGE HANDLER =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    user_id = update.effective_user.id
    
    if update.message.reply_to_message is not None:
        await reply_handler(update, context)
        return
    
    partner_id = get_partner(user_id)
    
    if partner_id is None:
        gender, _ = get_user_gender(user_id)
        if not gender:
            await update.message.reply_text(
                "⚠️ Please select your gender first!",
                parse_mode='Markdown',
                reply_markup=gender_keyboard()
            )
        else:
            await update.message.reply_text("❌ Not in a chat. Use /search to find a partner.")
        return
    
    is_premium = check_premium(user_id)
    
    try:
        if is_premium:
            await context.bot.send_message(
                chat_id=partner_id,
                text="⭐ *Premium*\n\n" + update.message.text,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=partner_id,
                text=update.message.text
            )
    except Forbidden:
        stop_chat(user_id)
        remove_user(partner_id)
        await update.message.reply_text("❌ Partner left. Use /search.")
    except Exception as e:
        print(f"❌ Send error: {e}")
        await update.message.reply_text("❌ Failed to send message.")

# ================= BUTTON =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    # Handle gender callback
    if data.startswith("gender_"):
        await gender_callback(update, context)
        return
    
    # Handle referral copy
    if data == "copy_referral":
        code = get_referral_code(user_id)
        if code:
            bot_username = context.bot.username
            referral_link = f"https://t.me/{bot_username}?start={code}"
            text = f"Join me on Anonymous Chat!\n{referral_link}"
            await query.edit_message_text(
                f"📋 *Copy this text:*\n\n"
                f"`{text}`\n\n"
                f"Share it with your friends! 🎉",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="referral_back")]
                ])
            )
        return
    
    if data == "referral_back":
        await referral_callback(update, context)
        return
    
    if data == "referral_stats":
        count, referred = get_referral_stats(user_id)
        text = (
            f"📊 *Referral Stats*\n\n"
            f"Total referred: {count}\n"
            f"Extra chats: +{count * 5}\n"
        )
        if referred:
            text += f"\n📋 Recent referrals:\n"
            for uid, created_at in referred[:5]:
                text += f"• `{uid}` joined {created_at.strftime('%d/%m')}\n"
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="referral_back")]
            ])
        )
        return
    
    # Handle premium
    if data.startswith('premium_'):
        if data == 'premium_help':
            await query.edit_message_text(
                f"💳 *Cara Bayar Premium dengan Telegram Stars*\n\n"
                f"📌 *Langkah-langkah:*\n\n"
                f"1️⃣ *Beli Telegram Stars* dulu\n"
                f"   🔵 *fund.tg*\n\n"
                f"2️⃣ *Kembali ke bot ini*\n\n"
                f"3️⃣ *Pilih paket premium* di bawah\n\n"
                f"4️⃣ *Bayar dengan Stars* (konfirmasi pembayaran)\n\n"
                f"5️⃣ *Premium aktif!* 🎉\n\n"
                f"📋 *User ID Anda:* `{user_id}`\n"
                f"   (Salin ID ini jika perlu hubungi admin)\n\n"
                f"💡 *Tips:* Beli Stars di [Fragment](https://fragment.com) lebih murah!\n"
                f"💰 1 Star ≈ $0.013 (nilai setelah biaya)\n\n"
                f"📱 *Minimal withdraw:* 1000 Stars\n"
                f"⏳ *Masa tunggu withdraw:* 21 hari",
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=premium_keyboard()
            )
            return
        
        days = int(data.split('_')[1])
        
        await context.bot.send_invoice(
            chat_id=user_id,
            title=f"Premium {days} Hari",
            description=f"Premium {days} hari!\n♾️ Unlimited partners!\n⏳ No daily limit!",
            payload=f"premium_{days}",
            provider_token="",
            currency="XTR",
            prices=[{"label": f"{days} Hari", "amount": days * 2}],
            start_parameter="premium_subscription"
        )
        return
    
    # Handle feedback
    partner_id = get_partner(user_id)
    if partner_id:
        try:
            save_feedback(from_user=user_id, to_user=partner_id, feedback=data)
            await query.edit_message_text("✅ Thank you for your feedback!")
        except Exception as e:
            print(e)
    else:
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