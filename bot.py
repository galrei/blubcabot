import asyncio
import logging
import os
from html import escape

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

# Membaca file .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN belum ditemukan. "
        "Pastikan file .env berada di folder yang sama dengan bot.py."
    )

# Membuat folder logs jika belum tersedia
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


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
        "/meme - Menampilkan meme\n"
        "/cuaca <kota> - Melihat cuaca\n"
        "/admin - Mengecek status admin"
    )


async def meme(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "😄 Fitur meme belum dikonfigurasi."
    )


async def weather(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Gunakan format:\n/cuaca Jakarta"
        )
        return

    city = " ".join(context.args)

    try:
        response = requests.get(
            f"https://wttr.in/{city}",
            params={"format": "3"},
            timeout=10,
        )
        response.raise_for_status()

        result = response.text.strip()

        if not result:
            result = "Data cuaca tidak ditemukan."

        await update.message.reply_text(result)

    except requests.RequestException:
        logger.exception("Gagal mengambil data cuaca")

        await update.message.reply_text(
            "Maaf, data cuaca sedang tidak tersedia."
        )


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
        logger.exception("Gagal memeriksa status admin")

        await update.message.reply_text(
            "Status admin tidak dapat diperiksa."
        )


async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    if update.message.text is None:
        return

    # Escape agar teks pengguna aman ketika memakai HTML parse mode
    text = escape(update.message.text)

    await update.message.reply_text(
        f"<b>Pesan Anda:</b>\n{text}",
        parse_mode=ParseMode.HTML,
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Terjadi error saat memproses update: %s",
        context.error,
        exc_info=context.error,
    )


def main() -> None:
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

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

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            echo,
        )
    )

    application.add_error_handler(error_handler)

    logger.info("BlubcaBot mulai dijalankan")

    # Perbaikan khusus Python 3.14:
    # buat event loop secara manual sebelum run_polling().
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES
        )
    finally:
        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    main()
