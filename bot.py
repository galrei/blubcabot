import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Muat variabel dari file .env
load_dotenv()

# Ambil nilai dari .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Handler untuk /start
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update.message.reply_text(
        f"Halo, {user.first_name}! 👋\n"
        "Saya adalah BlubcaBot!\n"
        "Ketik /help untuk melihat daftar perintah."
    )

# ... (sisanya tetap sama seperti sebelumnya)
