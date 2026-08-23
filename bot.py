import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)
from config import BOT_TOKEN

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Handler untuk perintah /start
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update.message.reply_text(
        f"Halo, {user.first_name}! 👋\n"
        "Saya adalah BlubcaBot!\n"
        "Ketik /help untuk melihat daftar perintah."
    )

# Handler untuk perintah /help
def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "📜 **Daftar Perintah BlubcaBot:**\n"
        "/start - Mulai bot\n"
        "/help - Bantuan\n"
        "/meme - Kirim meme acak\n"
        "/cuaca - Cek cuaca (gunakan /cuaca [kota])\n"
        "/admin - Perintah admin (hanya untuk admin grup)"
    )

# Handler untuk pesan teks biasa
def echo(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)

# Handler untuk perintah /meme
def send_meme(update: Update, context: CallbackContext) -> None:
    meme_url = "https://i.imgur.com/4Z4Z4Z4.jpg"  # Ganti dengan URL meme
    update.message.reply_photo(photo=meme_url)

# Handler untuk perintah /cuaca (contoh sederhana)
def get_weather(update: Update, context: CallbackContext) -> None:
    if not context.args:
        update.message.reply_text("Gunakan: /cuaca [nama_kota]")
        return

    city = " ".join(context.args)
    update.message.reply_text(f"🌤️ Cuaca di {city} saat ini: Cerah (contoh)")

# Handler untuk perintah admin (contoh)
def admin_command(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.message.from_user.id):
        update.message.reply_text("❌ Anda bukan admin!")
        return

    update.message.reply_text("✅ Anda adalah admin!")

def is_admin(user_id: int) -> bool:
    # Ganti dengan daftar admin yang diizinkan
    ADMIN_IDS = [123456789]  # ID Telegram admin
    return user_id in ADMIN_IDS

def main() -> None:
    """Jalankan bot."""
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Handler perintah
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("meme", send_meme))
    dispatcher.add_handler(CommandHandler("cuaca", get_weather))
    dispatcher.add_handler(CommandHandler("admin", admin_command))

    # Handler pesan teks
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Mulai bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
