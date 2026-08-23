import asyncio
import logging
import os
import random
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

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_MEME_SIZE = 10 * 1024 * 1024  # Maksimal 10 MB


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
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Halo! Saya BlubcaBot.\n\n"
        "Gunakan /help untuk melihat daftar perintah."
    )


# =========================================================
# /help
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Daftar perintah:\n\n"
        "/start - Memulai bot\n"
        "/help - Menampilkan bantuan\n"
        "/meme - Mengirim meme secara acak\n"
        "/cuaca <kota> - Melihat cuaca\n"
        "/admin - Mengecek status admin grup"
    )


# =========================================================
# /meme
# =========================================================

async def meme(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    # Membuat folder jika belum ada
    if not MEME_FOLDER.exists():
        MEME_FOLDER.mkdir(parents=True, exist_ok=True)

        await update.message.reply_text(
            "Folder meme belum berisi gambar.\n\n"
            "Masukkan file gambar ke folder:\n"
            "assets/memes/"
        )
        return

    # Mengambil file gambar yang valid
    meme_files = [
        file
        for file in MEME_FOLDER.iterdir()
        if (
            file.is_file()
            and file.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
            and file.stat().st_size <= MAX_MEME_SIZE
        )
    ]

    if not meme_files:
        await update.message.reply_text(
            "Belum ada meme yang tersedia.\n\n"
            "Masukkan gambar dengan format:\n"
            ".jpg, .jpeg, .png, atau .webp\n\n"
            "ke folder assets/memes/"
        )
        return

    # Mengambil nama meme yang terakhir dikirim di chat ini
    last_meme = context.chat_data.get("last_meme")

    # Menghapus meme terakhir dari daftar pilihan
    available_memes = [
        file
        for file in meme_files
        if file.name != last_meme
    ]

    # Jika hanya ada satu file, gunakan file tersebut
    if not available_memes:
        available_memes = meme_files

    # Memilih meme secara acak
    selected_meme = random.choice(available_memes)

    # Menyimpan meme terakhir agar tidak langsung terulang
    context.chat_data["last_meme"] = selected_meme.name

    try:
        with selected_meme.open("rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"😂 {selected_meme.stem}",
            )

        logger.info(
            "Meme berhasil dikirim: %s",
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

async def weather(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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

        result = response.text.strip()

        if not result:
            result = "Data cuaca tidak ditemukan."

        await update.message.reply_text(result)

        logger.info(
            "Data cuaca dikirim untuk: %s",
            city,
        )

    except requests.RequestException:
        logger.exception(
            "Gagal mengambil data cuaca untuk: %s",
            city,
        )

        await update.message.reply_text(
            "Maaf, data cuaca sedang tidak tersedia."
        )


# =========================================================
# /admin
# =========================================================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    if update.effective_chat is None:
        return

    if update.effective_user is None:
        return

    try:
        member = await update.effective_chat.get_member(
            update.effective_user.id
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            await update.message.reply_text(
                "✅ Anda adalah admin grup."
            )
        else:
            await update.message.reply_text(
                "❌ Anda bukan admin grup."
            )

    except Exception:
        logger.exception(
            "Gagal memeriksa status admin"
        )

        await update.message.reply_text(
            "Status admin tidak dapat diperiksa."
        )


# =========================================================
# PESAN TEKS BIASA
# =========================================================

async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    if update.message.text is None:
        return

    safe_text = escape(update.message.text)

    await update.message.reply_text(
        f"<b>Pesan Anda:</b>\n{safe_text}",
        parse_mode=ParseMode.HTML,
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Terjadi error saat memproses update: %s",
        context.error,
        exc_info=context.error,
    )


# =========================================================
# FUNGSI UTAMA
# =========================================================

def main() -> None:
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Mendaftarkan command
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("meme", meme)
    )

    application.add_handler(
        CommandHandler("cuaca", weather)
    )

    application.add_handler(
        CommandHandler("admin", admin)
    )

    # Menangani pesan teks biasa
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            echo,
        )
    )

    # Mendaftarkan error handler
    application.add_error_handler(error_handler)

    logger.info("BlubcaBot mulai dijalankan")

    print("BlubcaBot berhasil terhubung dan sedang berjalan...")

    # Perbaikan event loop untuk Python 3.14
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES
        )

    except KeyboardInterrupt:
        print("\nBlubcaBot dihentikan.")

    finally:
        asyncio.set_event_loop(None)
        loop.close()


# =========================================================
# MENJALANKAN PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
