import asyncio
import logging
import os
from html import escape
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# KONFIGURASI
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN belum ditemukan. "
        "Pastikan file .env berada di folder yang sama dengan bot.py."
    )

BASE_DIR = Path(__file__).parent
MEME_FOLDER = BASE_DIR / "assets" / "memes"

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024   # 50 MB


# =========================================================
# LOGGING
# =========================================================

LOG_FOLDER = BASE_DIR / "logs"
LOG_FOLDER.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FOLDER / "bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# FUNGSI BANTUAN
# =========================================================

def get_meme_files() -> list[Path]:
    """Mengambil semua file meme yang valid dan diurutkan berdasarkan nama."""
    if not MEME_FOLDER.exists():
        MEME_FOLDER.mkdir(parents=True, exist_ok=True)
        return []

    files = []
    for file in MEME_FOLDER.iterdir():
        if not file.is_file():
            continue

        ext = file.suffix.lower()
        size = file.stat().st_size

        if ext in ALLOWED_IMAGE_EXTENSIONS and size <= MAX_IMAGE_SIZE:
            files.append(file)
        elif ext in ALLOWED_VIDEO_EXTENSIONS and size <= MAX_VIDEO_SIZE:
            files.append(file)

    # Urutkan berdasarkan nama file (A-Z)
    return sorted(files, key=lambda x: x.name.lower())


def get_description(meme_path: Path) -> str:
    """Mengambil deskripsi/POV dari file .txt yang sama namanya."""
    txt_file = meme_path.with_suffix(".txt")
    if txt_file.exists() and txt_file.is_file():
        try:
            return txt_file.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


# =========================================================
# /start
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Halo! Saya BlubcaBot.\n\n"
        "Gunakan /help untuk melihat daftar perintah."
    )


# =========================================================
# /help
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Daftar perintah:\n\n"
        "/start - Memulai bot\n"
        "/help - Menampilkan bantuan\n"
        "/meme - Mengirim meme berikutnya (berurutan)\n"
        "/cuaca <kota> - Melihat cuaca\n"
        "/admin - Mengecek status admin grup\n\n"
        "Cara menambah deskripsi/POV:\n"
        "Buat file .txt dengan nama yang sama dengan media.\n"
        "Contoh: kucing_lucu.mp4 → kucing_lucu.txt"
    )


# =========================================================
# /meme (BERURUTAN + DESKRIPSI)
# =========================================================

async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    meme_files = get_meme_files()

    if not meme_files:
        await update.message.reply_text(
            "Belum ada meme yang tersedia.\n\n"
            "Masukkan file dengan format:\n"
            "• Gambar: .jpg, .jpeg, .png, .webp (max 10 MB)\n"
            "• Video : .mp4, .mov, .avi, .mkv, .webm (max 50 MB)\n\n"
            "ke folder assets/memes/\n\n"
            "Tips: Buat file .txt dengan nama yang sama untuk menambah deskripsi/POV."
        )
        return

    # Ambil index terakhir di chat ini
    last_index = context.chat_data.get("last_meme_index", -1)

    # Pilih meme berikutnya (berurutan)
    next_index = (last_index + 1) % len(meme_files)
    selected_meme = meme_files[next_index]

    # Simpan index terbaru
    context.chat_data["last_meme_index"] = next_index

    # Ambil deskripsi/POV
    description = get_description(selected_meme)

    # Buat caption
    if description:
        caption = f"😂 {selected_meme.stem}\n\n{description}"
    else:
        caption = f"😂 {selected_meme.stem}"

    try:
        with selected_meme.open("rb") as media:
            ext = selected_meme.suffix.lower()

            if ext in ALLOWED_IMAGE_EXTENSIONS:
                await update.message.reply_photo(
                    photo=media,
                    caption=caption,
                )
            else:
                await update.message.reply_video(
                    video=media,
                    caption=caption,
                    supports_streaming=True,
                )

        logger.info(
            "Meme berhasil dikirim (index %s): %s",
            next_index,
            selected_meme.name,
        )

    except Exception:
        logger.exception(
            "Gagal mengirim meme: %s",
            selected_meme.name,
        )
        await update.message.reply_text(
            "Gagal mengirim meme. Silakan coba lagi."
        )


# =========================================================
# /cuaca
# =========================================================

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Gunakan format:\n"
            "/cuaca Jakarta"
        )
        return

    city = " ".join(context.args)

    await update.message.reply_text(
        f"Sedang mengambil data cuaca untuk {city}..."
    )

    try:
        response = requests.get(
            f"https://wttr.in/{city}",
            params={
                "format": (
                    "Lokasi: %l\n"
                    "Cuaca: %C\n"
                    "Suhu: %t\n"
                    "Terasa seperti: %f\n"
                    "Angin: %w"
                )
            },
            timeout=10,
        )

        response.raise_for_status()
        result = response.text.strip() or "Data cuaca tidak ditemukan."

        await update.message.reply_text(result)
        logger.info("Data cuaca dikirim untuk: %s", city)

    except requests.RequestException:
        logger.exception("Gagal mengambil data cuaca untuk: %s", city)
        await update.message.reply_text(
            "Maaf, data cuaca sedang tidak tersedia."
        )


# =========================================================
# /admin
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if update.effective_chat is None or update.effective_user is None:
        return

    try:
        member = await update.effective_chat.get_member(
            update.effective_user.id
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await update.message.reply_text("✅ Anda adalah admin grup.")
        else:
            await update.message.reply_text("❌ Anda bukan admin grup.")

    except Exception:
        logger.exception("Gagal memeriksa status admin")
        await update.message.reply_text(
            "Status admin tidak dapat diperiksa."
        )


# =========================================================
# PESAN TEKS BIASA
# =========================================================

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return

    safe_text = escape(update.message.text)
    await update.message.reply_text(
        f"<b>Pesan Anda:</b>\n{safe_text}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(
        "Terjadi error saat memproses update: %s",
        context.error,
        exc_info=context.error,
    )


# =========================================================
# FUNGSI UTAMA
# =========================================================

def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("meme", meme))
    application.add_handler(CommandHandler("cuaca", weather))
    application.add_handler(CommandHandler("admin", admin))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
    )

    application.add_error_handler(error_handler)

    logger.info("BlubcaBot mulai dijalankan")
    print("BlubcaBot berhasil terhubung dan sedang berjalan...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nBlubcaBot dihentikan.")
    finally:
        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    main()
