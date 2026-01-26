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
TELEGRAM_BOT_TOKEN = "8551885799:AAFwzXsK8xuc0HPgVjCK1HdyGPMT9gVZLwo"

# Appwrite Config
APPWRITE_ENDPOINT = "https://fra.cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID = "692c7cce0036aa32cb12"
APPWRITE_API_KEY = "standard_e1eb40bc704c26bff01939550bfa18f741d15a704b92ef416769d1f92f5c3358cc37d716261dcc9d775ab20375e1a51288a3330ba0156f385e60748932446e7ff2e64678b0454d9a8883fe2f38f1311278969e045c1328b829e58e55fa090e1e3d2b12d6df904438709c9b6b97cbeafc14e5ff4f533b9f565f33fe3824369814"
APPWRITE_DB_ID = "697299e8002cc13b21b4"
APPWRITE_COLLECTION_ID = "data"

# API Config
API_URL = "https://api.x10.network/numapi.php"
API_KEY = "num_devil"

# ------------------------------------------------------------------
# 🌐 DUMMY WEB SERVER (FOR RENDER FREE TIER)
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Alive!"

def run_web_server():
    # Render assigns the port automatically in the environment variable 'PORT'
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
    await update.message.reply_text("🚀 **Bot is Online!**\nSend `/num <number>`", parse_mode=ParseMode.MARKDOWN)

async def search_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/num 9876543210`", parse_mode=ParseMode.MARKDOWN)
        return

    searched_number = context.args[0]
    status_msg = await update.message.reply_text(f"🔍 Searching `{searched_number}`...", parse_mode=ParseMode.MARKDOWN)
    results = fetch_data(searched_number)
    
    if not results:
        await status_msg.edit_text("❌ No data found.")
        return

    response_text = f"📂 **Results for {searched_number}:**\n\n"
    has_valid_data = False

    for p in results:
        raw_name = p.get("name")
        if not raw_name or str(raw_name).strip() in ["", "N/A"]: continue
        
        has_valid_data = True
        result_mobile = str(p.get("mobile", searched_number))
        clean_address = str(p.get("address", "N/A")).replace("!", ", ").replace(" ,", ",").strip()[:250]

        record = {
            'name': str(raw_name),
            'fname': str(p.get("father_name", "N/A")),
            'mobile': result_mobile,
            'address': clean_address
        }

        status = save_to_appwrite(record, result_mobile)
        db_status = "✅ Saved" if status == "success" else ("🔁 Exists" if status == "duplicate" else "⚠️ Error")

        response_text += (
            f"📱 **Mobile:** `{record['mobile']}`\n"
            f"👤 **Name:** {record['name']}\n"
            f"👴 **Father:** {record['fname']}\n"
            f"🏠 **Address:** {record['address']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    if has_valid_data:
        if len(response_text) > 4000: response_text = response_text[:4000] + "\n...(truncated)"
        await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await status_msg.edit_text("⚠️ Data found but contained invalid names (N/A).")

# ------------------------------------------------------------------
# ▶️ MAIN EXECUTION
# ------------------------------------------------------------------

if __name__ == '__main__':
    if "YOUR_TELEGRAM_BOT_TOKEN" in TELEGRAM_BOT_TOKEN:
        print("❌ ERROR: Add Token in line 18!")
        exit()

    # 1. Start the Dummy Web Server in a separate thread
    print("🌍 Starting Dummy Web Server...")
    threading.Thread(target=run_web_server).start()

    # 2. Start the Bot
    print("🔥 Bot Started...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("num", search_num))
    application.run_polling()
