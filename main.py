import logging
import requests
import threading
import os
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from appwrite.client import Client
from appwrite.services.databases import Databases
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------------------------------------------------------
# ⚙️ CONFIGURATION
# ------------------------------------------------------------------
# ⚠️ PASTE YOUR TELEGRAM BOT TOKEN BELOW
TELEGRAM_BOT_TOKEN = "8551885799:AAG1iqE8ObrqwETtjuYJhdw430TNoPGtqnc"

# Appwrite Config
APPWRITE_ENDPOINT = "https://fra.cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID = "697814dc00318b052e40"
APPWRITE_API_KEY = "standard_d568cc436f162ea258544b826d81f125ee5439fef59bb25bd975d0ccb06e696cf35afe619bb747290151129a1001162a2aa7447ae9d681b03321e072d987b442a8637628d034a90512ad9e9c4354ccaf7d4382a7a094cf8018f517917a76c46c629ddab6958a830e5bbf8d689e09b7dc8bda484ff06f55cdcc57d7ce4c4d6a98"
APPWRITE_DB_ID = "69781519001bb396e648"
APPWRITE_COLLECTION_ID = "scrap"

# API Config
# UPDATED API URL
API_URL = "https://api.paanel.shop/numapi.php"
API_KEY = "num_wanted"

# Owner Config
OWNER_TAG = "@Hamza3895"

# ------------------------------------------------------------------
# 🌐 DUMMY WEB SERVER (FOR RENDER DEPLOYMENT)
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Alive!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------
# 🔌 SETUP
# ------------------------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

session = requests.Session()
retry_strategy = Retry(
    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

# ------------------------------------------------------------------
# 🛠 HELPER FUNCTIONS
# ------------------------------------------------------------------

def fetch_data(mobile_number):
    try:
        # Params construct the full URL: ...php?action=api&key=num_wanted&number=...
        params = {"action": "api", "key": API_KEY, "number": mobile_number}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"}
        response = session.get(API_URL, params=params, headers=headers, timeout=20)
        try:
            data = response.json()
        except:
            return []
        
        # New API returns a list directly, this handles it perfectly
        if isinstance(data, list): return data
        elif isinstance(data, dict):
            if data.get('error') or data.get('response') == 'error': return []
            return [data]
        return []
    except Exception as e:
        logging.error(f"API Fetch Error: {e}")
        return []

def save_to_appwrite(data_dict, doc_id):
    try:
        databases.create_document(APPWRITE_DB_ID, APPWRITE_COLLECTION_ID, doc_id, data_dict)
        return "success"
    except Exception as e:
        if "409" in str(e): return "duplicate"
        logging.error(f"Appwrite DB Error: {e}")
        return "error"

# ------------------------------------------------------------------
# 🤖 BOT HANDLERS
# ------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"👋 **Welcome to Nightmare for Strangers Bot!**\n\n"
        f"🔎 **How to Use:**\n"
        f"Send `/num` followed by the mobile number.\n"
        f"Example: `/num 9876543210`\n\n"
        f"👨‍💻 **Developer:** {OWNER_TAG}\n"
        f"🆘 **Help/Contact:** {OWNER_TAG}"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def search_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"⚠️ **Usage Error**\nPlease send: `/num 9876543210`", parse_mode=ParseMode.MARKDOWN)
        return

    searched_number = context.args[0]
    status_msg = await update.message.reply_text(f"🔍 **Searching:** `{searched_number}` ...", parse_mode=ParseMode.MARKDOWN)
    
    results = fetch_data(searched_number)
    
    if not results:
        await status_msg.edit_text("❌ **No data found.**")
        return

    response_text = f"📂 **Results for {searched_number}:**\n\n"
    has_valid_data = False

    for p in results:
        raw_name = p.get("name")
        # Strict N/A Check
        if not raw_name or str(raw_name).strip() in ["", "N/A", "null", "None"]: 
            continue
        
        has_valid_data = True
        result_mobile = str(p.get("mobile", searched_number))
        
        # New API uses "!" in address, this replace logic handles it correctly
        clean_address = str(p.get("address", "N/A")).replace("!", ", ").replace(" ,", ",").strip()[:250]

        record = {
            'name': str(raw_name),
            'fname': str(p.get("father_name", "N/A")),
            'mobile': result_mobile,
            'address': clean_address
        }

        # Database Save
        status = save_to_appwrite(record, result_mobile)
        
        # Status Icon Logic
        if status == "success": db_status = "✅ Saved"
        elif status == "duplicate": db_status = "🔁 Exists"
        else: db_status = "⚠️ Error"

        # Build Card
        response_text += (
            f"📱 **Mobile:** `{record['mobile']}`\n"
            f"👤 **Name:** `{record['name']}`\n"
            f"👴 **Father:** {record['fname']}\n"
            f"🏠 **Address:** {record['address']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    # Footer
    response_text += f"\n🤖 **Bot by {OWNER_TAG}**"

    if has_valid_data:
        if len(response_text) > 4000: response_text = response_text[:4000] + "\n...(truncated)"
        await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await status_msg.edit_text("❌ **No data found.**")

# ------------------------------------------------------------------
# ▶️ MAIN EXECUTION
# ------------------------------------------------------------------

if __name__ == '__main__':
    if "YOUR_TELEGRAM_BOT_TOKEN" in TELEGRAM_BOT_TOKEN:
        print("❌ ERROR: Please paste your Telegram Bot Token in line 18!")
        exit()

    # 1. Start Web Server (For Render)
    print("🌍 Starting Web Server...")
    threading.Thread(target=run_web_server).start()

    # 2. Start Bot
    print("🔥 Bot Started...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("num", search_num))
    application.run_polling()
