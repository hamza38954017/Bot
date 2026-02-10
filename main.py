import logging
import requests
import threading
import os
import asyncio
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
APPWRITE_PROJECT_ID = "6986cc890027e3b7def9"
APPWRITE_API_KEY = "standard_72cdac3120d700c22823ff92201c9ba3ebf6a35cfab43d5dce97a4bbe8867ead1d95740a84c15dd052ff4b733a2bcd7c72b3cf36c39cbe69fd58504ea77b881b95d41556bdb25c1ce890477039d83436075c65c52c54680c6c511259e81958bb793afb19da6ac4bbccbce40f8ce687e7acb42aa77248187535bca7b2465bf570"
APPWRITE_DB_ID = "6986cd6f00356b66de5d"
APPWRITE_COLLECTION_ID = "hell"

# API Config
API_URL = "https://api.paanel.shop/numapi.php"
API_KEY = "ahsjyash"

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
        params = {"action": "api", "key": API_KEY, "number": mobile_number}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"}
        
        response = session.get(API_URL, params=params, headers=headers, timeout=20)
        try:
            data = response.json()
        except:
            return []
        
        # 1. New API Format: {"results": [...], "status": true}
        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            return data["results"]
        # 2. Legacy: List
        elif isinstance(data, list):
            return data
        # 3. Legacy: Single Dict
        elif isinstance(data, dict):
            if data.get('error') or data.get('response') == 'error': 
                return []
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
    
    # Run API fetch in a separate thread to avoid blocking the bot
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, fetch_data, searched_number)
    
    if not results:
        await status_msg.edit_text("❌ **No data found.**")
        return

    response_text = f"📂 **Results for {searched_number}:**\n\n"
    has_valid_data = False
    
    # Keep track of valid entries to avoid duplicate text in message
    valid_entries_count = 0

    for p in results:
        # -------------------------------------------------------
        # 🛡️ STRICT VALIDATION (MATCHING SCRAPER LOGIC)
        # -------------------------------------------------------
        raw_name = str(p.get("name", "")).strip()
        # Look for 'fname' first, fallback to 'father_name'
        raw_fname = str(p.get("fname", p.get("father_name", ""))).strip()
        raw_address = str(p.get("address", "")).strip()

        bad_values = ["", "N/A", "n/a", "None", "null", "NULL"]

        # If ANY key field is bad, skip the entire record
        if (raw_name in bad_values) or (raw_fname in bad_values) or (raw_address in bad_values):
            continue
        
        has_valid_data = True
        valid_entries_count += 1
        
        result_mobile = str(p.get("mobile", searched_number))
        
        # Clean Address
        clean_address = raw_address.replace("!", ", ").replace(" ,", ",").strip()
        if len(clean_address) > 250: clean_address = clean_address[:250]

        record = {
            'name': raw_name,
            'fname': raw_fname,
            'mobile': result_mobile,
            'address': clean_address
        }

        # Database Save (Run in executor to avoid blocking)
        status = await loop.run_in_executor(None, save_to_appwrite, record, result_mobile)

        # Build Card
        response_text += (
            f"📱 **Mobile:** `{record['mobile']}`\n"
            f"👤 **Name:** `{record['name']}`\n"
            f"👴 **Father:** {record['fname']}\n"
            f"🏠 **Address:** {record['address']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        
        # Limit message length to avoid Telegram limits
        if valid_entries_count >= 5:
            response_text += "\n⚠️ *Result limit reached...*"
            break

    # Footer
    response_text += f"\n🤖 **Bot by {OWNER_TAG}**"

    if has_valid_data:
        if len(response_text) > 4000: 
            response_text = response_text[:4000] + "\n...(truncated)"
        await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await status_msg.edit_text(f"❌ **No valid data found.**\n(Data was found but filtered due to 'N/A' fields)")

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
