import logging
import json
import os
import random
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from keep_alive import keep_alive
# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants for conversation states
(
    MAIN_MENU,
    ANON_COMMENT,
    CRASH_REPORT,
    ANON_CONFESSION,
    CRUSH_SELECT,
    CRUSH_MESSAGE,
    REQUEST_COINS,
    REPLY_TO_MESSAGE,
) = range(8)

# Data files
DATA_FILE = 'bot_data.json'
CHATS_FILE = 'chats_data.json'
CHANNEL_USERNAME = "@CrushYaabGUT"

# Load or initialize data
def load_data() -> Dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                # Ensure message_history exists
                if 'message_history' not in data:
                    data['message_history'] = {}
                return data
    except Exception as e:
        logger.error(f"Error loading data: {e}")
    return {
        'main_admin': None,
        'admins': {},
        'admin_requests': {},
        'users': {},
        'coin_requests': {},
        'invites': {},
        'message_history': {},  # Now guaranteed to exist
    }

def load_chats() -> Dict:
    try:
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chats: {e}")
    return {
        'crush_messages': [],
        'comments': [],
        'confessions': [],
        'crash_reports': [],
    }

def save_data(data: Dict) -> None:
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def save_chats(chats: Dict) -> None:
    try:
        with open(CHATS_FILE, 'w') as f:
            json.dump(chats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving chats: {e}")

# Initialize data
bot_data = load_data()
chats_data = load_chats()

# Helper functions
def get_user_data(user_id: int) -> Dict:
    if str(user_id) not in bot_data['users']:
        bot_data['users'][str(user_id)] = {
            'coins': 0,
            'invite_code': str(uuid.uuid4())[:8],
            'invited': 0,
            'blocked': False,
            'message_count': 0,
            'username': None,
        }
    return bot_data['users'][str(user_id)]

def is_main_admin(user_id: int) -> bool:
    return bot_data['main_admin'] == str(user_id)

def is_admin(user_id: int) -> bool:
    return str(user_id) in bot_data['admins'] or is_main_admin(user_id)

def add_coins(user_id: int, amount: int) -> None:
    user_data = get_user_data(user_id)
    user_data['coins'] += amount
    save_data(bot_data)

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📝پیام ناشناس به کراشتون📝")],
        [KeyboardButton("📝کامنت ناشناس در کانال📝")],
        [KeyboardButton("❤️کراش یابی❤️")],
        [KeyboardButton("🗣️اعتراف ناشناس🗣️")],
        [KeyboardButton("🪙سکه ها🪙")],
    ]
    if is_main_admin(None):
        buttons.append([KeyboardButton("👑 Admin Panel")])
    elif is_admin(None):
        buttons.append([KeyboardButton("🛡️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📊 Admin List")],
        [KeyboardButton("📝 View Comments")],
        [KeyboardButton("💔 View Crash Reports")],
        [KeyboardButton("🗣️ View Confessions")],
        [KeyboardButton("🪙 View Coin Requests")],
        [KeyboardButton("🔙 Main Menu")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_user_display_name(user_id: int, user_data: Dict) -> str:
    """Get a display name for the user that's not their numeric ID"""
    if user_data.get('username'):
        return f"@{user_data['username']}"
    elif user_data.get('name'):
        return user_data['name']
    else:
        return f"User-{user_data['invite_code']}"

# Command handlers
async def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    message = update.effective_message

    # Check user requirements
    if not await check_user_requirements(update, context):
        return ConversationHandler.END

    # Update user data with current info
    user_data = get_user_data(user.id)
    user_data['name'] = user.full_name
    user_data['username'] = user.username
    save_data(bot_data)

    # Check if user came from an invite link
    if context.args and len(context.args) == 1:
        invite_code = context.args[0]
        for uid, u_data in bot_data['users'].items():
            if u_data['invite_code'] == invite_code:
                add_coins(int(uid), 10)
                u_data['invited'] += 1
                save_data(bot_data)
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🎉 یک نفر از دوست هات با استفاده از لینک دعوت تو به ربات پیوست. بهت 10 سکه دادم. کل سکه هات برابر اند با: {bot_data['users'][uid]['coins']}"
                    )
                except Exception as e:
                    logger.error(f"Error notifying inviter: {e}")
                break

    welcome_text = (
        f"👋 خوش اومدی {user.first_name}!\n\n"
        "📌 برای استفاده از ربات باید از دکمه های زیر استفاده کنی:\n"
        "📝پیام ناشناس به کراشتون📝 - ارسال پیام ناشناس به کراشتون(باید در حال استفاده از ربات باشه)\n"
        "📝کامنت ناشناس در کانال📝 - ارسال کامنت ناشناس در کانال\n"
        "❤️کراش یابی❤️ - پیام دادن برای شناسایی کراشتون به صورت ناشناس در کانال\n"
        "🗣️اعتراف ناشناس🗣️ - میتونی به صورت ناشناس توی کانال اعتراف کنی\n"
        "🪙سکه ها🪙 - تعداد سکه هات رو ببین و سکه رایگان به دست بیار\n\n"
        f"💰 موجودی سکه های شما: {user_data['coins']}\n"
        f"📤 لینک دعوت شما: https://t.me/{context.bot.username}?start={user_data['invite_code']}"
    )

    await message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())
    return MAIN_MENU

    welcome_text = (
        f"👋 خوش اومدی {user.first_name}!\n\n"
        "📌 برای استفاده از ربات باید از دکمه های زیر استفاده کنی:\n"
        "📝پیام ناشناس به کراشتون📝 - ارسال پیام ناشناس به کراشتون(باید در حال استفاده از ربات باشه)\n"
        "📝کامنت ناشناس در کانال📝 - ارسال کامنت ناشناس در کانال\n"
        "❤️کراش یابی❤️ - پیام دادن برای شناسایی کراشتون به صورت ناشناس در کانال\n"
        "🗣️اعتراف ناشناس🗣️ - میتونی به صورت ناشناس توی کانال اعتراف کنی\n"
        "🪙سکه ها🪙 - تعداد سکه هات رو ببین و سکه رایگان به دست بیار\n\n"
        f"💰 موجودی سکه های شما: {user_data['coins']}\n"
        f"📤 لینک دعوت شما: https://t.me/{context.bot.username}?start={user_data['invite_code']}"
    )

    await message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())
    return MAIN_MENU

async def imadmin(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if bot_data['main_admin'] is None:
        bot_data['main_admin'] = str(user.id)
        save_data(bot_data)
        await update.message.reply_text(
            "👑 You are now the main admin!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text("❌ یک ادمین اصلی وجود دارد.❌")

async def letmeadmin(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if is_admin(user.id):
        await update.message.reply_text("ℹ️ شما در حال حاضر ادمین هستید")
        return

    if str(user.id) in bot_data['admin_requests']:
        await update.message.reply_text("ℹ️ شما قبلا یک درخواست ادمین شدن ارسال کرده اید")
        return

    bot_data['admin_requests'][str(user.id)] = {'name': user.full_name, 'date': str(datetime.now())}
    save_data(bot_data)

    if bot_data['main_admin']:
        try:
            await context.bot.send_message(
                chat_id=bot_data['main_admin'],
                text=f"🛡️ New admin request from {user.full_name} (@{user.username or 'no_username'})",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user.id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{user.id}"),
                    ]
                ])
            )
        except Exception as e:
            logger.error(f"Error sending admin request to main admin: {e}")

    await update.message.reply_text("✅ درخواست ادمینی شما با موفقیت به ادمین اصلی فرستاده شد. منتظر تایید باشید")

async def adlist(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return

    if not bot_data['admins']:
        await update.message.reply_text("ℹ️ ادمین دیگری وجود ندارد")
        return

    admins_text = "🛡️ Admin List:\n\n"
    for admin_id, admin_data in bot_data['admins'].items():
        admins_text += f"👤 {admin_data['name']} (ID: {admin_id})\n"
        admins_text += f"📅 Since: {admin_data['date']}\n"
        admins_text += f"📊 Activity: {admin_data.get('activity', 0)} actions\n\n"

    await update.message.reply_text(
        admins_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑️ Remove {admin_data['name']}", callback_data=f"remove_admin_{admin_id}")]
            for admin_id, admin_data in bot_data['admins'].items()
        ])
    )

async def view_comments(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return

    if not chats_data['comments']:
        await update.message.reply_text("ℹ️ امکا ارسال کامنت وجود ندارد")
        return

    for idx, comment in enumerate(chats_data['comments']):
        if not comment.get('processed', False):
            await update.message.reply_text(
                f"📝 Comment #{idx+1}:\n\n{comment['text']}\n\n"
                f"🕒 Submitted at: {comment['date']}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_comment_{idx}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_comment_{idx}"),
                    ]
                ])
            )

async def view_crash_reports(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return

    if not chats_data['crash_reports']:
        await update.message.reply_text("ℹ️ امکان ارسال پیام کراشیابی وجود ندارد")
        return

    for idx, report in enumerate(chats_data['crash_reports']):
        if not report.get('processed', False):
            await update.message.reply_text(
                f"💔 Crash Report #{idx+1}:\n\n{report['text']}\n\n"
                f"🕒 Submitted at: {report['date']}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_crash_{idx}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_crash_{idx}"),
                    ]
                ])
            )

async def view_confessions(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return

    if not chats_data['confessions']:
        await update.message.reply_text("ℹ️ شما در حال حاضر نمیتوانید اعتراف کنید")
        return

    for idx, confession in enumerate(chats_data['confessions']):
        if not confession.get('processed', False):
            await update.message.reply_text(
                f"🗣️ Confession #{idx+1}:\n\n{confession['text']}\n\n"
                f"🕒 Submitted at: {confession['date']}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_confession_{idx}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_confession_{idx}"),
                    ]
                ])
            )

async def view_coin_requests(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return

    if not bot_data['coin_requests']:
        await update.message.reply_text("ℹ️ شما نمیتوانید برای سکه رایگان درخواست دهید")
        return

    for user_id, request in bot_data['coin_requests'].items():
        if not request.get('processed', False):
            await update.message.reply_text(
                f"🪙 Coin Request from User ID: {user_id}\n\n"
                f"🕒 Requested at: {request['date']}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_coins_{user_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_coins_{user_id}"),
                    ]
                ])
            )

async def main_menu(update: Update, context: CallbackContext) -> int:
    if not await check_user_requirements(update, context):
        return ConversationHandler.END
    text = update.message.text
    user = update.effective_user

    if text == "📝پیام ناشناس به کراشتون📝":
        user_data = get_user_data(user.id)
        if user_data['coins'] < 1:
            await update.message.reply_text("❌ برای پیام دادن به کراشت به 1 سکهنیاز داری عزیزم. یا از ادمین قرض بگیر و یا یک نفر رو به ربات دعوت کن تا 10 سکه بگیری")
            return MAIN_MENU

        # Get list of active users (excluding self and bots)
        active_users = []
        for uid, u_data in bot_data['users'].items():
            if int(uid) != user.id and not u_data.get('blocked', False):
                try:
                    chat_member = await context.bot.get_chat_member(int(uid), int(uid))
                    if chat_member.status != 'left' and chat_member.status != 'kicked':
                        display_name = get_user_display_name(int(uid), u_data)
                        active_users.append((int(uid), display_name))
                except Exception as e:
                    logger.error(f"Error checking user {uid}: {e}")

        if not active_users:
            await update.message.reply_text("ℹ️ کاربر فعالی برای کانال وجود ندارد")
            return MAIN_MENU

        keyboard = [
            [InlineKeyboardButton(f"{name}", callback_data=f"crush_select_{uid}")]
            for uid, name in active_users[:50]  # Limit to 50 users to avoid too large keyboard
        ]

        await update.message.reply_text(
            "💌 Select your crush:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CRUSH_SELECT

    elif text == "📝کامنت ناشناس در کانال📝":
        await update.message.reply_text(
            "📝 لطفا متن کامنت ناشناس خودتون رو ارسال کنید(حداکثر 500 کاراکتر):\n\n"
            "   ",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)
        )
        return ANON_COMMENT

    elif text == "❤️کراش یابی❤️":
        await update.message.reply_text(
            "لطفا متن کراشیابی خودتون رو ارسال کنید(حداکثر 500 کاراکتر):\n\n"
            "   ",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)
        )
        return CRASH_REPORT

    elif text == "🗣️اعتراف ناشناس🗣️":
        await update.message.reply_text(
            "اعتراف کن ولی بیشتر از 500 کارکتر نباشه:\n\n"
            "Y   ",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)
        )
        return ANON_CONFESSION

    elif text == "🪙سکه ها🪙":
        await update.message.reply_text(
            "🪙سکه ها🪙 Options:\n\n"
            "1. دعوت از دوتات - لینک دعوتت رو برای دوستات بفرست و بابت عضو شدن هر کدوم از دوستات، 10 سکه رایگان بگیر\n"
            f"   اینم لینک دعوتت: https://t.me/{context.bot.username}?start={get_user_data(user.id)['invite_code']}\n\n"
            "2. از ادمین های دست و دلبازمون سکه قرض بگیر. هر بار دو سکه\n\n"
            f"💰مقدار سکه هات: {get_user_data(user.id)['coins']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Request Free Coins", callback_data="request_coins")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
            ])
        )
        return MAIN_MENU

    elif text in ["👑 Admin Panel", "🛡️ Admin Panel"]:
        if not is_admin(user.id):
            await update.message.reply_text("❌ You don't have permission to access the admin panel.")
            return MAIN_MENU

        await update.message.reply_text(
            "🛡️ Admin Panel",
            reply_markup=get_admin_keyboard()
        )
        return MAIN_MENU

    # Handle replies to messages
    elif update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        # Check if this is a reply to a message from the bot
        original_text = update.message.reply_to_message.text
        if "You received an anonymous message from" in original_text:
            # This is a reply to a crush message
            sender_id = None
            for msg in chats_data['crush_messages']:
                if msg['to'] == str(user.id) and msg['text'] in original_text:
                    sender_id = msg['from']
                    break

            if sender_id:
                context.user_data['replying_to'] = sender_id
                await update.message.reply_text(
                    f"✏️ You're replying to {get_user_display_name(int(sender_id), bot_data['users'].get(sender_id, {}))}\n"
                    "Please type your reply message:",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)
                )
                return REPLY_TO_MESSAGE
            else:
                await update.message.reply_text("❌ Could not find the original message sender.")
        else:
            await update.message.reply_text("❌ You can only reply to messages you received from this bot.")

    return MAIN_MENU

async def admin_panel(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    user = update.effective_user

    if text == "📊 Admin List":
        await adlist(update, context)
    elif text == "📝 View Comments":
        await view_comments(update, context)
    elif text == "💔 View Crash Reports":
        await view_crash_reports(update, context)
    elif text == "🗣️ View Confessions":
        await view_confessions(update, context)
    elif text == "🪙 View Coin Requests":
        await view_coin_requests(update, context)
    elif text == "🔙 Main Menu":
        await update.message.reply_text("🏠 Main Menu", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    return MAIN_MENU

async def crush_select(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        await query.edit_message_text("🏠 Main Menu")
        await query.message.reply_text("🏠 Main Menu", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    if query.data.startswith("crush_select_"):
        crush_id = query.data.split("_")[-1]
        context.user_data['crush_id'] = crush_id

        # Get crush display name
        crush_data = get_user_data(int(crush_id))
        crush_name = get_user_display_name(int(crush_id), crush_data)

        await query.edit_message_text(
            f"💌 لطفا پیامی که میخوای به ای کاربر بفرستی رو ارسال کن عزیزم {crush_name} (max 300 characters):\n\n"
            "   "
        )
        return CRUSH_MESSAGE

    return CRUSH_SELECT

async def crush_message(update: Update, context: CallbackContext) -> int:
    user = update.effective_user

    if update.message.text == "/cancel" or update.message.text == "❌ Cancel":
        await update.message.reply_text("❌ Message canceled.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    if len(update.message.text) > 300:
        await update.message.reply_text("❌ Message is too long (max 300 characters). Please try again.")
        return CRUSH_MESSAGE

    crush_id = context.user_data.get('crush_id')
    if not crush_id:
        await update.message.reply_text("❌ هنوز کسی رو انتخاب نکردی، دوباره تلاش کن")
        return MAIN_MENU

    user_data = get_user_data(user.id)
    if user_data['coins'] < 1:
        await update.message.reply_text("شما برای ارسال این پیام سکه کافی ندارید")
        return MAIN_MENU

    user_data['coins'] -= 1
    save_data(bot_data)

    # Get crush display name and sender display name
    crush_data = get_user_data(int(crush_id))
    crush_name = get_user_display_name(int(crush_id), crush_data)
    sender_name = get_user_display_name(user.id, user_data)

    # Save message
    message_id = str(uuid.uuid4())
    chats_data['crush_messages'].append({
        'id': message_id,
        'from': str(user.id),
        'from_name': sender_name,
        'to': crush_id,
        'to_name': crush_name,
        'text': update.message.text,
        'date': str(datetime.now()),
        'replied': False
    })
    save_chats(chats_data)

    # Initialize message_history if it doesn't exist
    if 'message_history' not in bot_data:
        bot_data['message_history'] = {}

    # Save to message history for replies
    if crush_id not in bot_data['message_history']:
        bot_data['message_history'][crush_id] = []

    bot_data['message_history'][crush_id].append({
        'id': message_id,
        'from': str(user.id),
        'text': update.message.text,
        'time': str(datetime.now())
    })
    save_data(bot_data)

    # Send to crush
    try:
        sent_msg = await context.bot.send_message(
            chat_id=crush_id,
            text=f"💌 شما پیام ناشناسی از این کاربر دریافت کردید. این کاربر شما رو کراش خودش میدونه و این پیام رو ارسال کرده {sender_name}:\n\n{update.message.text}\n\n"
                 "   "
        )

        # Save the message ID for tracking replies
        for msg in chats_data['crush_messages']:
            if msg['id'] == message_id:
                msg['bot_message_id'] = sent_msg.message_id
                break
        save_chats(chats_data)

    except Exception as e:
        logger.error(f"Error sending crush message: {e}")
        await update.message.reply_text("message sent")
        return MAIN_MENU

    # Notify main admin
    if bot_data['main_admin']:
        try:
            await context.bot.send_message(
                chat_id=bot_data['main_admin'],
                text=f"💌 کراش مسیج جدید:\n\nFrom: {sender_name} (ID: {user.id})\n"
                     f"To: {crush_name} (ID: {crush_id})\n\nMessage: {update.message.text}"
            )
        except Exception as e:
            logger.error(f"Error notifying main admin about crush message: {e}")

    await update.message.reply_text(
        f"✅ پیام شما به صورت ناشناس به این کاربر ارسال شد {crush_name}!",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def reply_to_message(update: Update, context: CallbackContext) -> int:
    user = update.effective_user

    if update.message.text == "/cancel" or update.message.text == "❌ Cancel":
        await update.message.reply_text("❌ Reply canceled.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    sender_id = context.user_data.get('replying_to')
    if not sender_id:
        await update.message.reply_text("❌ Error: Could not find original sender. Please try again.")
        return MAIN_MENU

    # Get sender and recipient display names
    sender_data = get_user_data(int(sender_id))
    sender_name = get_user_display_name(int(sender_id), sender_data)
    user_data = get_user_data(user.id)
    user_name = get_user_display_name(user.id, user_data)

    # Send the reply
    try:
        sent_msg = await context.bot.send_message(
            chat_id=sender_id,
            text=f"💌 You received a reply from {user_name}:\n\n{update.message.text}\n\n"
                 "     "
        )

        # Update the original message as replied
        for msg in chats_data['crush_messages']:
            if msg['from'] == sender_id and msg['to'] == str(user.id) and not msg.get('replied', False):
                msg['replied'] = True
                msg['reply_text'] = update.message.text
                msg['reply_time'] = str(datetime.now())
                break
        save_chats(chats_data)

        # Save to message history for further replies
        if sender_id not in bot_data['message_history']:
            bot_data['message_history'][sender_id] = []
        bot_data['message_history'][sender_id].append({
            'from': str(user.id),
            'text': update.message.text,
            'time': str(datetime.now()),
            'is_reply': True
        })
        save_data(bot_data)

    except Exception as e:
        logger.error(f"Error sending reply message: {e}")
        await update.message.reply_text("⚠️ Failed to send reply. The user may have blocked the bot.")
        return MAIN_MENU

    await update.message.reply_text(
        f"✅ Your reply has been sent to {sender_name}!",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def anon_comment(update: Update, context: CallbackContext) -> int:
    user = update.effective_user

    if update.message.text == "/cancel" or update.message.text == "❌ Cancel":
        await update.message.reply_text("❌ Comment canceled.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    if len(update.message.text) > 500:
        await update.message.reply_text("❌ Comment is too long (max 500 characters). Please try again.")
        return ANON_COMMENT

    # Save comment for admin approval
    chats_data['comments'].append({
        'from': str(user.id),
        'text': update.message.text,
        'date': str(datetime.now()),
        'processed': False,
        'approved': False
    })
    save_chats(chats_data)

    # Notify admins
    for admin_id in [bot_data['main_admin']] + list(bot_data['admins'].keys()):
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📝 کامنت ناشناس جدید:\n\n{update.message.text}\n\n"
                         f"🕒 Submitted at: {chats_data['comments'][-1]['date']}",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_comment_{len(chats_data['comments'])-1}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_comment_{len(chats_data['comments'])-1}"),
                        ]
                    ])
                )
            except Exception as e:
                logger.error(f"Error sending comment to admin {admin_id}: {e}")

    await update.message.reply_text(
        "✅ کامنت شما برای بررسی به ادمین ارسال شد. بعد از بررسی در کانال گذاشته میشه",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def crash_report(update: Update, context: CallbackContext) -> int:
    user = update.effective_user

    if update.message.text == "/cancel" or update.message.text == "❌ Cancel":
        await update.message.reply_text("❌ Report canceled.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    if len(update.message.text) > 500:
        await update.message.reply_text("❌ Report is too long (max 500 characters). Please try again.")
        return CRASH_REPORT

    # Save crash report for admin approval
    chats_data['crash_reports'].append({
        'from': str(user.id),
        'text': update.message.text,
        'date': str(datetime.now()),
        'processed': False,
        'approved': False
    })
    save_chats(chats_data)

    # Notify admins
    for admin_id in [bot_data['main_admin']] + list(bot_data['admins'].keys()):
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"کراشیابی جدید:\n\n{update.message.text}\n\n"
                         f"🕒 Submitted at: {chats_data['crash_reports'][-1]['date']}",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_crash_{len(chats_data['crash_reports'])-1}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_crash_{len(chats_data['crash_reports'])-1}"),
                        ]
                    ])
                )
            except Exception as e:
                logger.error(f"Error sending crash report to admin {admin_id}: {e}")

    await update.message.reply_text(
        "✅ کراشیابی شما به ادمین فرستاده شد. بعد از تایید توی کانال گذاشته میشه",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def anon_confession(update: Update, context: CallbackContext) -> int:
    user = update.effective_user

    if update.message.text == "/cancel" or update.message.text == "❌ Cancel":
        await update.message.reply_text("❌ Confession canceled.", reply_markup=get_main_menu_keyboard())
        return MAIN_MENU

    if len(update.message.text) > 500:
        await update.message.reply_text("❌ Confession is too long (max 500 characters). Please try again.")
        return ANON_CONFESSION

    # Save confession for admin approval
    chats_data['confessions'].append({
        'from': str(user.id),
        'text': update.message.text,
        'date': str(datetime.now()),
        'processed': False,
        'approved': False
    })
    save_chats(chats_data)

    # Notify admins
    for admin_id in [bot_data['main_admin']] + list(bot_data['admins'].keys()):
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🗣️ اعتراف جدید:\n\n{update.message.text}\n\n"
                         f"🕒 Submitted at: {chats_data['confessions'][-1]['date']}",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_confession_{len(chats_data['confessions'])-1}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_confession_{len(chats_data['confessions'])-1}"),
                        ]
                    ])
                )
            except Exception as e:
                logger.error(f"Error sending confession to admin {admin_id}: {e}")

    await update.message.reply_text(
        "✅ اعتراف شما برای بررسی به ادمین فرستاده شد. بعد از تایید توی کانال گذاشته میشه",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN_MENU

async def request_coins(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = str(user.id)

    if query.data == "request_coins":
        # Check for existing pending request
        if user_id in bot_data['coin_requests'] and not bot_data['coin_requests'][user_id].get('processed', False):
            await query.edit_message_text("ℹ️ You already have a pending coin request.")
            return

        # Create new request
        bot_data['coin_requests'][user_id] = {
            'name': user.full_name,
            'date': str(datetime.now()),
            'processed': False,
            'approved': False
        }
        save_data(bot_data)

        # Notify all admins
        notified = False
        for admin_id in [bot_data['main_admin']] + list(bot_data['admins'].keys()):
            if admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🪙 درخواست سکه رایگان از {user.full_name} (ID: {user.id})\n\n"
                             f"🕒 Requested at: {bot_data['coin_requests'][user_id]['date']}",
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("✅ Approve", callback_data=f"approve_coins_{user.id}"),
                                InlineKeyboardButton("❌ Reject", callback_data=f"reject_coins_{user.id}"),
                            ]
                        ])
                    )
                    notified = True
                except Exception as e:
                    logger.error(f"Error sending coin request to admin {admin_id}: {e}")

        if notified:
            await query.edit_message_text("✅ بعد از بررسی درخواست توسط ادمین، دو سکه به حسابتان واریز می شود")
        else:
            await query.edit_message_text("⚠️ Could not notify any admins. Please try again later.")
            # Remove the request if no admins were notified
            del bot_data['coin_requests'][user_id]
            save_data(bot_data)
    return MAIN_MENU

async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    try:
        # Admin approval handling
        if data.startswith("admin_approve_"):
            if not is_main_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            req_user_id = data.split("_")[-1]
            if req_user_id not in bot_data['admin_requests']:
                await query.edit_message_text("ℹ️ This request has already been processed.")
                return

            bot_data['admins'][req_user_id] = {
                'name': bot_data['admin_requests'][req_user_id]['name'],
                'date': bot_data['admin_requests'][req_user_id]['date'],
                'activity': 0
            }
            del bot_data['admin_requests'][req_user_id]
            save_data(bot_data)

            try:
                await context.bot.send_message(
                    chat_id=req_user_id,
                    text="🎉 Your admin request has been approved! You now have admin privileges."
                )
            except Exception as e:
                logger.error(f"Error notifying new admin: {e}")

            await query.edit_message_text(f"✅ Admin request approved. {bot_data['admins'][req_user_id]['name']} is now an admin.")

        elif data.startswith("admin_reject_"):
            if not is_main_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            req_user_id = data.split("_")[-1]
            if req_user_id not in bot_data['admin_requests']:
                await query.edit_message_text("ℹ️ This request has already been processed.")
                return

            del bot_data['admin_requests'][req_user_id]
            save_data(bot_data)

            try:
                await context.bot.send_message(
                    chat_id=req_user_id,
                    text="❌ درخواست ادمین شدن شما رد شد"
                )
            except Exception as e:
                logger.error(f"Error notifying rejected admin: {e}")

            await query.edit_message_text("❌ Admin request rejected.")

        # Admin management
        elif data.startswith("remove_admin_"):
            if not is_main_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            admin_id = data.split("_")[-1]
            if admin_id not in bot_data['admins']:
                await query.edit_message_text("ℹ️ This admin doesn't exist.")
                return

            del bot_data['admins'][admin_id]
            save_data(bot_data)

            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text="⚠️ Your admin privileges have been removed by the main admin."
                )
            except Exception as e:
                logger.error(f"Error notifying removed admin: {e}")

            await query.edit_message_text("✅ ادمین با موفقیت حذف شد")

        # Comment approval system
        elif data.startswith("approve_comment_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            comment_idx = int(data.split("_")[-1])
            if comment_idx >= len(chats_data['comments']):
                await query.edit_message_text("ℹ️ This comment doesn't exist.")
                return

            if chats_data['comments'][comment_idx]['processed']:
                await query.edit_message_text("ℹ️ This comment has already been processed.")
                return

            chats_data['comments'][comment_idx]['processed'] = True
            chats_data['comments'][comment_idx]['approved'] = True
            chats_data['comments'][comment_idx]['approved_by'] = str(user.id)
            save_chats(chats_data)

            try:
                await context.bot.send_message(
                    chat_id="@CrushYaabGUT",
                    text=f"📝کامنت ناشناس در کانال📝:\n\n{chats_data['comments'][comment_idx]['text']}"
                )
                await query.edit_message_text("✅ کامنت شما تایید شد و در کانال گذاشته شد")
            except Exception as e:
                logger.error(f"Error posting comment to channel: {e}")
                if bot_data['main_admin']:
                    try:
                        await context.bot.send_message(
                            chat_id=bot_data['main_admin'],
                            text=f"📝 Approved Comment (failed to post to channel):\n\n{chats_data['comments'][comment_idx]['text']}"
                        )
                        await query.edit_message_text("✅ Comment approved but couldn't post to channel. Sent to main admin.")
                    except Exception as e2:
                        logger.error(f"Error notifying main admin: {e2}")
                        await query.edit_message_text("✅ Comment approved but couldn't post to channel or notify admin.")
                else:
                    await query.edit_message_text("✅ Comment approved but couldn't post to channel.")

        elif data.startswith("reject_comment_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            comment_idx = int(data.split("_")[-1])
            if comment_idx >= len(chats_data['comments']):
                await query.edit_message_text("ℹ️ This comment doesn't exist.")
                return

            if chats_data['comments'][comment_idx]['processed']:
                await query.edit_message_text("ℹ️ This comment has already been processed.")
                return

            chats_data['comments'][comment_idx]['processed'] = True
            chats_data['comments'][comment_idx]['approved'] = False
            chats_data['comments'][comment_idx]['rejected_by'] = str(user.id)
            save_chats(chats_data)

            await query.edit_message_text("❌ کامنت ناشناس شما رد شد. لطفا اسم کسی رو نبرید و یا فحاشی نکنید")

        # Crash report handling
        elif data.startswith("approve_crash_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            crash_idx = int(data.split("_")[-1])
            if crash_idx >= len(chats_data['crash_reports']):
                await query.edit_message_text("ℹ️ This report doesn't exist.")
                return

            if chats_data['crash_reports'][crash_idx]['processed']:
                await query.edit_message_text("ℹ️ This report has already been processed.")
                return

            chats_data['crash_reports'][crash_idx]['processed'] = True
            chats_data['crash_reports'][crash_idx]['approved'] = True
            chats_data['crash_reports'][crash_idx]['approved_by'] = str(user.id)
            save_chats(chats_data)

            try:
                await context.bot.send_message(
                    chat_id="@CrushYaabGUT",
                    text=f"کراشیابی❤:\n\n{chats_data['crash_reports'][crash_idx]['text']}"
                )
                await query.edit_message_text("✅ پیام کراشیابی شما تایید شد و به زودی در کانال قرار میگیرد")
            except Exception as e:
                logger.error(f"Error posting crush report to channel: {e}")
                if bot_data['main_admin']:
                    try:
                        await context.bot.send_message(
                            chat_id=bot_data['main_admin'],
                            text=f"💔 Approved Crush Report (failed to post to channel):\n\n{chats_data['crash_reports'][crash_idx]['text']}"
                        )
                        await query.edit_message_text("✅ Crash report approved but couldn't post to channel. Sent to main admin.")
                    except Exception as e2:
                        logger.error(f"Error notifying main admin: {e2}")
                        await query.edit_message_text("✅ Crash report approved but couldn't post to channel or notify admin.")
                else:
                    await query.edit_message_text("✅ Crash report approved but couldn't post to channel.")

        elif data.startswith("reject_crash_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            crash_idx = int(data.split("_")[-1])
            if crash_idx >= len(chats_data['crash_reports']):
                await query.edit_message_text("ℹ️ This report doesn't exist.")
                return

            if chats_data['crash_reports'][crash_idx]['processed']:
                await query.edit_message_text("ℹ️ This report has already been processed.")
                return

            chats_data['crash_reports'][crash_idx]['processed'] = True
            chats_data['crash_reports'][crash_idx]['approved'] = False
            chats_data['crash_reports'][crash_idx]['rejected_by'] = str(user.id)
            save_chats(chats_data)

            await query.edit_message_text("پیام کراشیابی شما رد شد. لطفا اسم کسی رو نبرید یا فحاشی نکنید")

        # Confession handling
        elif data.startswith("approve_confession_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            confession_idx = int(data.split("_")[-1])
            if confession_idx >= len(chats_data['confessions']):
                await query.edit_message_text("ℹ️ This confession doesn't exist.")
                return

            if chats_data['confessions'][confession_idx]['processed']:
                await query.edit_message_text("ℹ️ This confession has already been processed.")
                return

            chats_data['confessions'][confession_idx]['processed'] = True
            chats_data['confessions'][confession_idx]['approved'] = True
            chats_data['confessions'][confession_idx]['approved_by'] = str(user.id)
            save_chats(chats_data)

            try:
                await context.bot.send_message(
                    chat_id="@CrushYaabGUT",
                    text=f"🗣️اعتراف ناشناس🗣️:\n\n{chats_data['confessions'][confession_idx]['text']}"
                )
                await query.edit_message_text("✅ اعتراف شما تایید شد و در کانال قرار گرفت")
            except Exception as e:
                logger.error(f"Error posting confession to channel: {e}")
                if bot_data['main_admin']:
                    try:
                        await context.bot.send_message(
                            chat_id=bot_data['main_admin'],
                            text=f"🗣️ Approved Confession (failed to post to channel):\n\n{chats_data['confessions'][confession_idx]['text']}"
                        )
                        await query.edit_message_text("✅ Confession approved but couldn't post to channel. Sent to main admin.")
                    except Exception as e2:
                        logger.error(f"Error notifying main admin: {e2}")
                        await query.edit_message_text("✅ Confession approved but couldn't post to channel or notify admin.")
                else:
                    await query.edit_message_text("✅ Confession approved but couldn't post to channel.")

        elif data.startswith("reject_confession_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            confession_idx = int(data.split("_")[-1])
            if confession_idx >= len(chats_data['confessions']):
                await query.edit_message_text("ℹ️ This confession doesn't exist.")
                return

            if chats_data['confessions'][confession_idx]['processed']:
                await query.edit_message_text("ℹ️ This confession has already been processed.")
                return

            chats_data['confessions'][confession_idx]['processed'] = True
            chats_data['confessions'][confession_idx]['approved'] = False
            chats_data['confessions'][confession_idx]['rejected_by'] = str(user.id)
            save_chats(chats_data)

            await query.edit_message_text("اعتراف شما رد شد")

        # Coin request handling
        elif data.startswith("approve_coins_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            req_user_id = data.split("_")[-1]
            if req_user_id not in bot_data['coin_requests']:
                await query.edit_message_text("ℹ️ This request doesn't exist.")
                return

            if bot_data['coin_requests'][req_user_id]['processed']:
                await query.edit_message_text("ℹ️ This request has already been processed.")
                return

            # Process approval
            bot_data['coin_requests'][req_user_id]['processed'] = True
            bot_data['coin_requests'][req_user_id]['approved'] = True
            bot_data['coin_requests'][req_user_id]['approved_by'] = str(user.id)
            save_data(bot_data)

            # Add coins to user
            add_coins(int(req_user_id), 2)

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=req_user_id,
                    text="🎉 درخواست سکه رایگان شما توسط ادمین تایید شد. 2 سکه به حسابتون اضافه شد"
                )
                await query.edit_message_text("✅ Coin request approved. User received 2 coins.")
            except Exception as e:
                logger.error(f"Error notifying user about coin approval: {e}")
                await query.edit_message_text("✅ Coin request approved but couldn't notify user.")

        elif data.startswith("reject_coins_"):
            if not is_admin(user.id):
                await query.edit_message_text("❌ You don't have permission to do this.")
                return

            req_user_id = data.split("_")[-1]
            if req_user_id not in bot_data['coin_requests']:
                await query.edit_message_text("ℹ️ This request doesn't exist.")
                return

            if bot_data['coin_requests'][req_user_id]['processed']:
                await query.edit_message_text("ℹ️ This request has already been processed.")
                return

            # Process rejection
            bot_data['coin_requests'][req_user_id]['processed'] = True
            bot_data['coin_requests'][req_user_id]['approved'] = False
            bot_data['coin_requests'][req_user_id]['rejected_by'] = str(user.id)
            save_data(bot_data)

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=req_user_id,
                    text="❌ Your request for free coins has been rejected."
                )
                await query.edit_message_text("❌ Coin request rejected.")
            except Exception as e:
                logger.error(f"Error notifying user about coin rejection: {e}")
                await query.edit_message_text("❌ Coin request rejected but couldn't notify user.")

        # Main menu navigation
        elif data == "main_menu":
            await query.edit_message_text("🏠 Main Menu")
            await query.message.reply_text("🏠 Main Menu", reply_markup=get_main_menu_keyboard())

        # Coin request initiation
        elif data == "request_coins":
            if str(user.id) in bot_data['coin_requests'] and not bot_data['coin_requests'][str(user.id)].get('processed', False):
                await query.edit_message_text("ℹ️ You already have a pending coin request.")
                return

            bot_data['coin_requests'][str(user.id)] = {
                'name': user.full_name,
                'date': str(datetime.now()),
                'processed': False,
                'approved': False
            }
            save_data(bot_data)

            # Notify all admins
            notified = False
            for admin_id in [bot_data['main_admin']] + list(bot_data['admins'].keys()):
                if admin_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"🪙 New coin request from {user.full_name} (ID: {user.id})\n\n"
                                 f"🕒 Requested at: {bot_data['coin_requests'][str(user.id)]['date']}",
                            reply_markup=InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_coins_{user.id}"),
                                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_coins_{user.id}"),
                                ]
                            ])
                        )
                        notified = True
                    except Exception as e:
                        logger.error(f"Error sending coin request to admin {admin_id}: {e}")

            if notified:
                await query.edit_message_text("✅ درخواست سکه رایگان شما به ادمین ارسال شد")
            else:
                await query.edit_message_text("⚠️ Could not notify any admins. Please try again later.")
                # Remove the request if no admins were notified
                del bot_data['coin_requests'][str(user.id)]
                save_data(bot_data)

    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("⚠️ An error occurred. Please try again.")

async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        if bot_data['main_admin']:
            error_msg = f"⚠️ Bot error:\n\n{context.error}"
            await context.bot.send_message(chat_id=bot_data['main_admin'], text=error_msg)
    except Exception as e:
        logger.error(f"Error notifying admin about error: {e}")

async def check_user_requirements(update: Update, context: CallbackContext) -> bool:
    user = update.effective_user

    # Check if user has a non-numeric username
    if not user.username or user.username.isdigit():
        await update.message.reply_text(
            "❌ You must have a non-numeric username to use this bot.\n"
            "Please set a username in your Telegram settings and try again."
        )
        return False

    # Check if user is member of the channel
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        if member.status in ['left', 'kicked']:
            await update.message.reply_text(
                f"❌ You must join our channel @CrushYaabGUT use this bot.\n"
                f"Please join and try again."
            )
            return False
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        await update.message.reply_text(
            "⚠️ Could not verify channel membership. Please try again later."
        )
        return False

    return True
def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7656756450:AAEy4WOJ2lCt1mm21uJ_RteXGAXpX4r85uM").build()

    # Add conversation handler with the states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu),
                CommandHandler('start', start),
            ],
            CRUSH_SELECT: [
                CallbackQueryHandler(crush_select),
            ],
            CRUSH_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, crush_message),
                CommandHandler('cancel', lambda u, c: start(u, c)),
            ],
            REPLY_TO_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_message),
                CommandHandler('cancel', lambda u, c: start(u, c)),
            ],
            ANON_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, anon_comment),
                CommandHandler('cancel', lambda u, c: start(u, c)),
            ],
            CRASH_REPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, crash_report),
                CommandHandler('cancel', lambda u, c: start(u, c)),
            ],
            ANON_CONFESSION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, anon_confession),
                CommandHandler('cancel', lambda u, c: start(u, c)),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('imadmin', imadmin))
    application.add_handler(CommandHandler('letmeadmin', letmeadmin))
    application.add_handler(CommandHandler('adlist', adlist))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(request_coins, pattern="^request_coins$"))

    # Add error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    keep_alive()
    application.run_polling()

while True:
    main()
