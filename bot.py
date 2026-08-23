import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

# Muat variabel lingkungan dari file .env
load_dotenv()

# Ambil nilai dari .env (dengan error handling)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN tidak ditemukan di file .env!")

# Setup logging (simpan log ke file)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="logs/bot.log",  # Simpan log ke file
)
logger = logging.getLogger(__name__)

# ===== HANDLER UNTUK PERINTAH =====
def start(update: Update, context: CallbackContext) -> None:
    """Handler untuk perintah /start."""
    user = update.effective_user
    update.message.reply_text(
        f"👋 Halo, {user.first_name}!\n"
        "Saya adalah **BlubcaBot**!\n"
        "Ketik /help untuk melihat daftar perintah."
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Handler untuk perintah /help."""
    update.message.reply_text(
        "📜 **Daftar Perintah BlubcaBot:**\n\n"
        "🔹 /start - Mulai bot\n"
        "🔹 /help - Bantuan\n"
        "🔹 /meme - Kirim meme acak\n"
        "🔹 /cuaca [kota] - Cek cuaca (contoh: /cuaca Jakarta)\n"
        "🔹 /admin - Perintah admin (hanya untuk admin grup)\n\n"
        "💡 *Catatan: Beberapa fitur memerlukan API key (misal: cuaca)."
    )

def meme_command(update: Update, context: CallbackContext) -> None:
    """Handler untuk perintah /meme."""
    meme_url = "https://i.imgur.com/4Z4Z4Z4.jpg"  # Ganti dengan URL meme
    update.message.reply_photo(photo=meme_url)

def weather_command(update: Update, context: CallbackContext) -> None:
    """Handler untuk perintah /cuaca."""
    if not context.args:
        update.message.reply_text("❌ Gunakan: /cuaca [nama_kota]")
        return

    city = " ".join(context.args)
    update.message.reply_text(
        f"🌤️ Cuaca di **{city}** saat ini: Cerah (contoh)\n"
        "*Untuk fitur cuaca yang sebenarnya, gunakan API OpenWeatherMap."
    )

def admin_command(update: Update, context: CallbackContext) -> None:
    """Handler untuk perintah /admin (hanya untuk admin)."""
    if not is_admin(update.message.from_user.id):
        update.message.reply_text("❌ Anda bukan admin!")
        return

    update.message.reply_text("✅ Anda adalah admin!")

def is_admin(user_id: int) -> bool:
    """Cek apakah user adalah admin."""
    ADMIN_IDS = [123456789]  # Ganti dengan ID Telegram admin Anda
    return user_id in ADMIN_IDS

# ===== HANDLER UNTUK PESAN BIASA =====
def echo(update: Update, context: CallbackContext) -> None:
    """Handler untuk pesan teks biasa."""
    update.message.reply_text(f"💬 Anda bilang: {update.message.text}")

# ===== FUNGSI UTAMA =====
def main() -> None:
    """Jalankan bot dengan error handling."""
    try:
        # Inisialisasi bot
        updater = Updater(BOT_TOKEN)
        dispatcher = updater.dispatcher

        # Tambahkan handler
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("meme", meme_command))
        dispatcher.add_handler(CommandHandler("cuaca", weather_command))
        dispatcher.add_handler(CommandHandler("admin", admin_command))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

        # Mulai polling
        logger.info("🤖 Bot BlubcaBot sedang berjalan...")
        updater.start_polling()
        updater.idle()

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
