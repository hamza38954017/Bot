# @title 🚀 Run Professional Telegram Bot (Render Fixed Version)
import logging
import time
import requests
import threading
import os
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode, ChatType
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.exception import AppwriteException

# ------------------------------------------------------------------
# ⚙️ CONFIGURATION
# ------------------------------------------------------------------
BOT_TOKEN = "8551885799:AAEA8a7Cr2OPVFzuKss1WS4we7CnWEzNfyI"

# External API Config
API_URL = "https://api.x10.network/numapi.php"
API_KEY = "num_devil"

# Appwrite Database Config
APPWRITE_ENDPOINT = "https://fra.cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID = "692c7cce0036aa32cb12"
APPWRITE_API_KEY = "standard_e1eb40bc704c26bff01939550bfa18f741d15a704b92ef416769d1f92f5c3358cc37d716261dcc9d775ab20375e1a51288a3330ba0156f385e60748932446e7ff2e64678b0454d9a8883fe2f38f1311278969e045c1328b829e58e55fa090e1e3d2b12d6df904438709c9b6b97cbeafc14e5ff4f533b9f565f33fe3824369814"
APPWRITE_DB_ID = "697299e8002cc13b21b4"
APPWRITE_COLLECTION_ID = "data" 

# ------------------------------------------------------------------
# 🌐 KEEP ALIVE SERVER
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! Render Deployment."

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    # Render assigns a random PORT. We must listen on it.
    port = int(os.environ.get("PORT", 8080))
    # '0.0.0.0' tells Flask to listen on all public IPs (Required for Render)
    app.run(host='0.0.0.0', port=port)

# ------------------------------------------------------------------
# 🔧 SETUP
# ------------------------------------------------------------------

# REMOVED nest_asyncio (Not needed for Render)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Appwrite Client Setup
client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

user_cooldowns = {}
COOLDOWN_SECONDS = 5

# ------------------------------------------------------------------
# 🛠 HELPER FUNCTIONS
# ------------------------------------------------------------------

async def delete_delayed(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Background task to delete a message after 60 seconds."""
    await asyncio.sleep(60)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"🗑️ Auto-deleted message {message_id} in chat {chat_id}")
    except Exception as e:
        logging.warning(f"⚠️ Could not auto-delete message: {e}")

def save_to_appwrite(name, fname, mobile, address):
    """Saves data to Appwrite."""
    print(f"💾 Saving: {mobile}...") 
    try:
        data = {
            'name': str(name),
            'fname': str(fname),
            'mobile': str(mobile),
            'address': str(address)
        }
        databases.create_document(APPWRITE_DB_ID, APPWRITE_COLLECTION_ID, ID.unique(), data)
        return True
    except Exception as e:
        print(f"❌ APPWRITE ERROR: {str(e)}")
        return False

async def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔍 Search Number", callback_data='search_help'),
            InlineKeyboardButton("💎 Purchase API", callback_data='buy_api')
        ],
        [
            InlineKeyboardButton("⭐ About Bot", callback_data='about_bot'),
            InlineKeyboardButton("📞 Contact Admin", url="https://t.me/Hamza3895")
        ],
        [InlineKeyboardButton("🔄 Refresh Menu", callback_data='refresh')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_countdown_timer(update: Update, context: ContextTypes, remaining_time: int, original_message_id = None):
    for i in range(remaining_time, 0, -1):
        filled = "🟩" * (COOLDOWN_SECONDS - i)
        empty = "⬜" * i
        progress_bar = f"{filled}{empty}"
        countdown_msg = f"⏳ **COOLDOWN** ⏳\n\n⏰ Wait: `{i}`s\n{progress_bar}"

        if original_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=original_message_id,
                    text=countdown_msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        else:
            await update.message.reply_text(countdown_msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1)

    completion_msg = "✅ **Ready!** Use `/num <number>`"
    if original_message_id:
        try:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=original_message_id, text=completion_msg, parse_mode=ParseMode.MARKDOWN)
        except:
            pass

# ------------------------------------------------------------------
# 🎮 COMMAND HANDLERS
# ------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    commands = [
        BotCommand("start", "🚀 Start"),
        BotCommand("num", "🔍 Search"),
        BotCommand("menu", "📱 Menu"),
        BotCommand("api", "💎 Pricing")
    ]
    await context.bot.set_my_commands(commands)

    welcome_text = f"""
🌟 **WELCOME, {user.first_name}!** 🌟

🚀 *Number Details Bot* is ready!

🔍 **Features:**
✅ Find Name & Address
✅ 5s Cooldown active
✅ Shows ALL Linked Numbers

⚡ *Select an option:*
    """
    await update.message.reply_text(
        welcome_text,
        reply_markup=await get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📱 **MAIN MENU**",
        reply_markup=await get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def api_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows API pricing information."""
    await update.message.reply_text(
        "💎 **API PRICING**\nContact @Hamza3895\n💰 **Price:** ₹999",
        parse_mode=ParseMode.MARKDOWN
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'search_help':
        await query.message.edit_text(
            "🔍 **SEARCH GUIDE**\n\n📝 Use: `/num 9876543210`\n\n*5 seconds cooldown applies.*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_main')]])
        )

    elif query.data == 'buy_api':
        await query.message.edit_text(
            "💎 **PREMIUM API**\n\n💰 Price: ₹999 (Lifetime)\n🚀 Unlimited Requests",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/Hamza3895")],
                [InlineKeyboardButton("🔙 Back", callback_data='back_main')]
            ])
        )

    elif query.data == 'about_bot':
        await query.message.edit_text(
            "🤖 **ABOUT**\n\nVersion: 2.5\nDev: @Hamza3895\nStatus: Online ✅",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_main')]])
        )

    elif query.data in ['back_main', 'refresh']:
        await query.message.edit_text(
            "📱 **MAIN MENU**",
            reply_markup=await get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

async def num_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Cooldown Check
    current_time = time.time()
    if user_id in user_cooldowns:
        last_time = user_cooldowns[user_id].get('timestamp', 0)
        elapsed = current_time - last_time
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            msg = await update.message.reply_text(f"⏳ Wait {remaining}s...")
            await show_countdown_timer(update, context, remaining, msg.message_id)
            return

    user_cooldowns[user_id] = {'timestamp': current_time}

    if not context.args or not context.args[0].isdigit() or len(context.args[0]) != 10:
        await update.message.reply_text("❌ Usage: `/num 9999999999` (10 digits)", parse_mode=ParseMode.MARKDOWN)
        return

    mobile_number = context.args[0]
    search_msg = await update.message.reply_text(f"🔍 Searching `{mobile_number}`...", parse_mode=ParseMode.MARKDOWN)

    # Auto-Delete
    if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        asyncio.create_task(delete_delayed(context, update.effective_chat.id, search_msg.message_id))

    try:
        params = {"action": "api", "key": API_KEY, "number": mobile_number}
        response = requests.get(API_URL, params=params, timeout=15)
        data = response.json()

        outer = data.get("data", {})
        inner = outer.get("data", {})
        results = inner.get("results", [])

        if results:
            final_text = f"✅ **RESULTS FOR** `{mobile_number}`\n"
            count = 0

            for person in results:
                name = person.get("name", "N/A")
                fname = person.get("fname", "N/A")
                mob = person.get("mobile", "N/A")
                addr = person.get("address", "N/A")

                if count < 5:
                    final_text += f"\n📱 **Mobile:** `{mob}`\n👤 **Name:** `{name}`\n👨‍👦 **Father:** `{fname}`\n📍 **Addr:** `{addr}`\n──────────────────"

                save_to_appwrite(name, fname, mob, addr)
                count += 1

            if count > 5:
                final_text += f"\n...and {count - 5} records"

            final_text += "\n✨ **Credit : Dr. Hamza**"
            await search_msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN)

        else:
            await search_msg.edit_text("❌ No records found.", parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logging.error(f"API Error: {e}")
        await search_msg.edit_text("⚠️ Server Error.", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Use `/num <number>` to search.",
        reply_markup=await get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# ------------------------------------------------------------------
# ▶️ RUNNER (RENDER READY)
# ------------------------------------------------------------------

if __name__ == '__main__':
    # 1. Start Web Server in Background Thread
    # We must use '0.0.0.0' and os.environ.get("PORT") for Render
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    print("✅ Web Server Started.")

    # 2. Run Bot (Blocking Mode - No Loop Needed for Render)
    # Render will auto-restart the script if it crashes.
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', menu))
    application.add_handler(CommandHandler('num', num_handler))
    application.add_handler(CommandHandler('api', api_info))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is Polling...")
    application.run_polling()
