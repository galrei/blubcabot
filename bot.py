import asyncio
import io
import logging
import os
import re
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import InputMediaPhoto, InputMediaVideo, Update
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

# Regex untuk mendeteksi link Twitter/X dan CDN pbs.twimg.com
TWITTER_STATUS_REGEX = re.compile(
    r"https?://(?:www\.|mobile\.)?(?:twitter\.com|x\.com|fixupx\.com|fxtwitter\.com|vxtwitter\.com)/(?:#!/)?([a-zA-Z0-9_]+)/status/(\d+)",
    re.IGNORECASE,
)
TWIMG_IMAGE_REGEX = re.compile(
    r"https?://pbs\.twimg\.com/media/[^\s]+",
    re.IGNORECASE,
)
TWIMG_VIDEO_REGEX = re.compile(
    r"https?://video\.twimg\.com/[^\s]+",
    re.IGNORECASE,
)


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


def fetch_twitter_status(username: str, status_id: str) -> dict | None:
    """Mengambil informasi tweet dan media dari API fxtwitter/vxtwitter."""
    # 1. Coba api.fxtwitter.com
    try:
        url = f"https://api.fxtwitter.com/{username}/status/{status_id}"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            tweet = data.get("tweet")
            if tweet:
                author_data = tweet.get("author") or {}
                author_name = author_data.get("name", "𝕏 User")
                screen_name = author_data.get("screen_name", username)
                media_list = (tweet.get("media") or {}).get("all", [])

                formatted_media = []
                for m in media_list:
                    m_type = m.get("type")
                    m_url = m.get("url")
                    if m_url:
                        formatted_media.append({
                            "type": "video" if m_type in ("video", "gif") else "photo",
                            "url": m_url,
                        })

                return {
                    "author": f"{author_name} (@{screen_name})",
                    "text": tweet.get("text", "").strip(),
                    "url": tweet.get("url", f"https://x.com/{username}/status/{status_id}"),
                    "media": formatted_media,
                }
    except Exception as exc:
        logger.warning("Gagal mengambil status dari fxtwitter: %s", exc)

    # 2. Coba fallback ke api.vxtwitter.com
    try:
        url = f"https://api.vxtwitter.com/{username}/status/{status_id}"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            author_name = data.get("user_name", "𝕏 User")
            screen_name = data.get("user_screen_name", username)
            media_list = data.get("media_extended", [])

            formatted_media = []
            for m in media_list:
                m_type = m.get("type")
                m_url = m.get("url")
                if m_url:
                    formatted_media.append({
                        "type": "video" if m_type in ("video", "gif") else "photo",
                        "url": m_url,
                    })

            return {
                "author": f"{author_name} (@{screen_name})",
                "text": data.get("text", "").strip(),
                "url": data.get("tweetURL", f"https://x.com/{username}/status/{status_id}"),
                "media": formatted_media,
            }
    except Exception as exc:
        logger.warning("Gagal mengambil status dari vxtwitter: %s", exc)

    return None


def build_tweet_caption(author: str, text: str, tweet_url: str) -> str:
    """Menyusun caption berformat HTML dan membatasi panjangnya <= 1024 karakter."""
    escaped_author = escape(author)
    escaped_text = escape(text)

    prefix = f"👤 <b>{escaped_author}</b>\n\n"
    suffix = f'\n\n🔗 <a href="{tweet_url}">Buka di 𝕏</a>'

    full_caption = f"{prefix}{escaped_text}{suffix}" if escaped_text else f"{prefix.strip()}{suffix}"

    if len(full_caption) > 1024:
        max_text_len = 1024 - len(prefix) - len(suffix) - 3
        if max_text_len > 0:
            truncated_text = escaped_text[:max_text_len] + "..."
            full_caption = f"{prefix}{truncated_text}{suffix}"
        else:
            full_caption = f'🔗 <a href="{tweet_url}">Buka di 𝕏</a>'

    return full_caption


def download_media_stream(url: str) -> io.BytesIO | None:
    """Mengunduh file media ke dalam memory buffer (BytesIO)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=25,
        )
        resp.raise_for_status()
        buf = io.BytesIO(resp.content)
        content_type = resp.headers.get("content-type", "")
        if "video" in content_type or ".mp4" in url:
            buf.name = "media.mp4"
        else:
            buf.name = "media.jpg"
        return buf
    except Exception as exc:
        logger.error("Gagal mendownload media dari %s: %s", url, exc)
        return None


def download_with_ytdlp(url: str, output_path: str) -> tuple[bool, str]:
    """
    Mengunduh video menggunakan yt-dlp ke output_path.
    Mengembalikan (sukses: bool, pesan_error: str).
    Format yang dipilih: video terbaik ≤ 50 MB (mp4/webm) dengan fallback ke format terkecil.
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        "-f", "bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, ""
        err = (result.stderr or result.stdout or "Unknown error").strip()
        logger.warning("yt-dlp gagal untuk %s: %s", url, err)
        return False, err
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp timeout untuk %s", url)
        return False, "Proses download timeout."
    except Exception as exc:
        logger.error("Error saat menjalankan yt-dlp untuk %s: %s", url, exc)
        return False, str(exc)


async def process_generic_video(update: Update, url: str) -> bool:
    """
    Mengunduh dan mengirimkan video dari URL apapun menggunakan yt-dlp.
    Mendukung: YouTube, Streamrizz, HLS, dan ratusan situs video lainnya.
    """
    if update.message is None:
        return False

    status_msg = await update.message.reply_text(
        "⏳ Sedang mengunduh video, mohon tunggu...\n"
        "_(Proses ini bisa memakan waktu hingga 1-2 menit untuk video besar)_",
        parse_mode=ParseMode.HTML,
    )

    loop = asyncio.get_running_loop()

    # Jalankan yt-dlp di thread terpisah agar tidak memblokir event loop
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "video.%(ext)s")
        final_path_template = os.path.join(tmpdir, "video.mp4")

        success, err_msg = await loop.run_in_executor(
            None,
            download_with_ytdlp,
            url,
            output_path,
        )

        if not success:
            await status_msg.edit_text(
                f"❌ Gagal mengunduh video dari link tersebut.\n\n"
                f"<i>Kemungkinan penyebab: link tidak didukung, konten privat, atau format tidak tersedia.</i>",
                parse_mode=ParseMode.HTML,
            )
            return False

        # Cari file hasil unduhan (yt-dlp bisa menghasilkan .mp4, .webm, dst.)
        downloaded_files = list(Path(tmpdir).glob("video.*"))
        if not downloaded_files:
            await status_msg.edit_text(
                "❌ File video tidak ditemukan setelah proses unduhan.",
            )
            return False

        video_file = downloaded_files[0]
        file_size = video_file.stat().st_size

        # Cek batas ukuran Telegram (50 MB)
        if file_size > MAX_VIDEO_SIZE:
            await status_msg.edit_text(
                f"⚠️ Video terlalu besar untuk dikirim via Telegram "
                f"({file_size / (1024*1024):.1f} MB, batas 50 MB).\n\n"
                f'🔗 <a href="{escape(url)}">Buka link langsung</a>',
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            return False

        # Kirim video ke chat
        try:
            await status_msg.edit_text("📤 Mengirim video...")
            with open(video_file, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=f'📹 <b>Video</b>\n\n🔗 <a href="{escape(url)}">Link Sumber</a>',
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                )
            await status_msg.delete()
            return True
        except Exception:
            logger.exception("Gagal mengirim video dari %s", url)
            await status_msg.edit_text(
                "❌ Gagal mengirim video ke Telegram. Silakan coba lagi."
            )
            return False


async def process_x_status(update: Update, username: str, status_id: str) -> bool:
    """Memproses dan mengirimkan postingan dan media dari URL tweet 𝕏."""
    if update.message is None:
        return False

    status_msg = await update.message.reply_text("⏳ Sedang memproses konten dari 𝕏...")

    loop = asyncio.get_running_loop()
    tweet_data = await loop.run_in_executor(
        None,
        fetch_twitter_status,
        username,
        status_id,
    )

    if not tweet_data:
        await status_msg.edit_text(
            "❌ Gagal mengambil postingan 𝕏. Pastikan link benar dan postingan tidak diprivat/dihapus."
        )
        return False

    caption = build_tweet_caption(
        tweet_data["author"],
        tweet_data["text"],
        tweet_data["url"],
    )
    media_items = tweet_data.get("media", [])

    try:
        # Kasus 1: Tweet hanya teks tanpa gambar/video
        if not media_items:
            await status_msg.delete()
            await update.message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            return True

        # Kasus 2: Tweet memiliki 1 media tunggal (foto atau video)
        if len(media_items) == 1:
            item = media_items[0]
            if item["type"] == "video":
                try:
                    await update.message.reply_video(
                        video=item["url"],
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        supports_streaming=True,
                    )
                except Exception:
                    media_bytes = await loop.run_in_executor(
                        None,
                        download_media_stream,
                        item["url"],
                    )
                    if media_bytes:
                        await update.message.reply_video(
                            video=media_bytes,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            supports_streaming=True,
                        )
                    else:
                        raise
            else:
                try:
                    await update.message.reply_photo(
                        photo=item["url"],
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    media_bytes = await loop.run_in_executor(
                        None,
                        download_media_stream,
                        item["url"],
                    )
                    if media_bytes:
                        await update.message.reply_photo(
                            photo=media_bytes,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                        )
                    else:
                        raise

            await status_msg.delete()
            return True

        # Kasus 3: Tweet memiliki beberapa media (album / multi-photo)
        group = []
        for i, m in enumerate(media_items[:10]):
            item_caption = caption if i == 0 else None
            parse_mode = ParseMode.HTML if i == 0 else None
            if m["type"] == "video":
                group.append(
                    InputMediaVideo(
                        media=m["url"],
                        caption=item_caption,
                        parse_mode=parse_mode,
                    )
                )
            else:
                group.append(
                    InputMediaPhoto(
                        media=m["url"],
                        caption=item_caption,
                        parse_mode=parse_mode,
                    )
                )

        await update.message.reply_media_group(media=group)
        await status_msg.delete()
        return True

    except Exception:
        logger.exception("Error saat mengirim media tweet dari 𝕏")
        await status_msg.edit_text("❌ Gagal mengirim media dari link 𝕏 tersebut.")
        return False


async def process_x_direct_media(update: Update, media_url: str, media_type: str) -> bool:
    """Memproses dan mengirimkan gambar/video langsung dari CDN twimg."""
    if update.message is None:
        return False

    status_msg = await update.message.reply_text("⏳ Sedang memproses media 𝕏...")
    loop = asyncio.get_running_loop()

    try:
        if media_type == "photo":
            try:
                await update.message.reply_photo(
                    photo=media_url,
                    caption=f'🖼️ <b>Media dari 𝕏</b>\n\n🔗 <a href="{escape(media_url)}">Link Sumber</a>',
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                media_bytes = await loop.run_in_executor(
                    None,
                    download_media_stream,
                    media_url,
                )
                if media_bytes:
                    await update.message.reply_photo(
                        photo=media_bytes,
                        caption=f'🖼️ <b>Media dari 𝕏</b>\n\n🔗 <a href="{escape(media_url)}">Link Sumber</a>',
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    raise
        else:
            try:
                await update.message.reply_video(
                    video=media_url,
                    caption=f'📹 <b>Media dari 𝕏</b>\n\n🔗 <a href="{escape(media_url)}">Link Sumber</a>',
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                )
            except Exception:
                media_bytes = await loop.run_in_executor(
                    None,
                    download_media_stream,
                    media_url,
                )
                if media_bytes:
                    await update.message.reply_video(
                        video=media_bytes,
                        caption=f'📹 <b>Media dari 𝕏</b>\n\n🔗 <a href="{escape(media_url)}">Link Sumber</a>',
                        parse_mode=ParseMode.HTML,
                        supports_streaming=True,
                    )
                else:
                    raise

        await status_msg.delete()
        return True

    except Exception:
        logger.exception("Error saat memproses direct twimg media")
        await status_msg.edit_text("❌ Gagal memproses media dari URL tersebut.")
        return False


# =========================================================
# /start
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Halo! Saya BlubcaBot.\n\n"
        "Gunakan /help untuk melihat daftar perintah.\n"
        "Kirim link postingan 𝕏/Twitter untuk langsung melihat gambar atau videonya!"
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
        "/x <link> - Menampilkan gambar/video dari link 𝕏 (Twitter)\n"
        "/video <link> - Mengunduh & mengirim video dari link manapun\n"
        "   ↳ Alias: /dl\n"
        "/meme - Mengirim meme berikutnya (berurutan)\n"
        "/cuaca <kota> - Melihat cuaca\n"
        "/admin - Mengecek status admin grup\n\n"
        "💡 Kirim link 𝕏 langsung di chat untuk auto-preview!\n"
        "🎬 /video mendukung YouTube, TikTok, Streamrizz, Dailymotion, dll."
    )


# =========================================================
# /x & /twitter
# =========================================================

async def x_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Gunakan format:\n"
            "/x <link 𝕏/Twitter>\n\n"
            "Contoh:\n"
            "• /x https://x.com/galreio/status/2091497352704229874\n"
            "• /x https://pbs.twimg.com/media/HQZ9wREbQAAVZek?format=jpg&name=medium"
        )
        return

    url = context.args[0].strip()

    status_match = TWITTER_STATUS_REGEX.search(url)
    if status_match:
        username, status_id = status_match.groups()
        await process_x_status(update, username, status_id)
        return

    img_match = TWIMG_IMAGE_REGEX.search(url)
    if img_match:
        await process_x_direct_media(update, img_match.group(0), "photo")
        return

    vid_match = TWIMG_VIDEO_REGEX.search(url)
    if vid_match:
        await process_x_direct_media(update, vid_match.group(0), "video")
        return

    await update.message.reply_text(
        "❌ Link yang Anda masukkan bukan link postingan atau media 𝕏 / Twitter yang valid."
    )


# =========================================================
# /video & /dl – Universal video downloader
# =========================================================

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengunduh dan mengirimkan video dari berbagai platform menggunakan yt-dlp."""
    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text(
            "Gunakan format:\n"
            "/video <link video>\n\n"
            "Contoh:\n"
            "• /video https://streamrizz.com/d/8mj9idpoehft\n"
            "• /video https://youtu.be/dQw4w9WgXcQ\n"
            "• /video https://vm.tiktok.com/xxxxx\n\n"
            "💡 Mendukung ratusan situs video (YouTube, TikTok, Streamrizz, Dailymotion, dll.)"
        )
        return

    url = context.args[0].strip()

    # Validasi minimal bahwa input adalah URL
    if not re.match(r"https?://", url, re.IGNORECASE):
        await update.message.reply_text(
            "❌ Input harus berupa URL yang valid (dimulai dengan http:// atau https://)."
        )
        return

    await process_generic_video(update, url)


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
# HANDLER PESAN TEKS BIASA / AUTO-DETECT LINK 𝕏
# =========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return

    text = update.message.text

    # Deteksi otomatis link postingan 𝕏 / Twitter
    status_match = TWITTER_STATUS_REGEX.search(text)
    if status_match:
        username, status_id = status_match.groups()
        await process_x_status(update, username, status_id)
        return

    # Deteksi otomatis link gambar twimg langsung
    img_match = TWIMG_IMAGE_REGEX.search(text)
    if img_match:
        await process_x_direct_media(update, img_match.group(0), "photo")
        return

    # Deteksi otomatis link video twimg langsung
    vid_match = TWIMG_VIDEO_REGEX.search(text)
    if vid_match:
        await process_x_direct_media(update, vid_match.group(0), "video")
        return

    # Jika bukan link 𝕏, lakukan echo pesan
    safe_text = escape(text)
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
    application.add_handler(CommandHandler("x", x_command))
    application.add_handler(CommandHandler("twitter", x_command))
    application.add_handler(CommandHandler("video", video_command))
    application.add_handler(CommandHandler("dl", video_command))
    application.add_handler(CommandHandler("meme", meme))
    application.add_handler(CommandHandler("cuaca", weather))
    application.add_handler(CommandHandler("admin", admin))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
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

