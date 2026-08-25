# Struktur Direktori Proyek
```
blubcabot/
│
├── .gitignore          # File untuk mengabaikan file sensitif
├── README.md           # Dokumentasi proyek
├── requirements.txt    # Dependensi Python
├── config.py           # Konfigurasi bot (token, API keys)
├── bot.py              # Kode utama bot
└── assets/             # (Opsional) Gambar, suara, atau file pendukung
```

# 🤖 BlubcaBot - Telegram Bot

**BlubcaBot** adalah bot Telegram serbaguna dengan fitur pengiriman meme berurutan, informasi cuaca, manajemen admin grup, serta pembaca & penampil media (gambar & video) otomatis dari link **𝕏 (Twitter)**.

## 📌 Fitur
- 🔹 **𝕏 / Twitter Media Preview**: Membaca dan menampilkan gambar atau video dari postingan 𝕏 (Twitter) beserta caption dan link sumbernya.
  - Mendukung auto-detect link saat dikirimkan di chat.
  - Mendukung perintah `/x <link>` atau `/twitter <link>`.
  - Mendukung link postingan (misal: `https://x.com/galreio/status/2091497352704229874`) dan link media CDN langsung (`https://pbs.twimg.com/media/...`).
- 🔹 **Meme Berurutan**: Mengirim meme gambar/video dari folder `assets/memes/` lengkap dengan teks deskripsi/POV (`/meme`).
- 🔹 **Cek Cuaca**: Mengambil info cuaca kota secara real-time (`/cuaca <kota>`).
- 🔹 **Status Admin**: Mengecek status kepengurusan/admin grup (`/admin`).

## 🛠️ Cara Instalasi & Menjalankan Bot

### **Persyaratan**
- Python 3.8+
- Akun Telegram (untuk mendapatkan token bot via [@BotFather](https://t.me/BotFather))

### **Langkah-langkah**
1. **Clone repositori ini:**
   ```bash
   git clone https://github.com/galrei/blubcabot.git
   cd blubcabot
   ```

2. **Install dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Konfigurasi Environment (.env):**
   Buat file `.env` di direktori proyek dan isi dengan token bot Telegram Anda:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   ```

4. **Jalankan Bot:**
   ```bash
   python bot.py
   ```
   Atau jalankan file `jalankan_bot.bat` (di Windows).

## 📜 Struktur Proyek
```
blubcabot/
├── .env                 # File environment (token bot, dsb.)
├── .gitignore           # File yang diabaikan Git
├── README.md            # Dokumentasi proyek
├── requirements.txt     # Dependensi Python
├── config.py            # Konfigurasi opsional
├── bot.py               # Logika utama bot Telegram
├── jalankan_bot.bat     # Batch script untuk menjalankan bot di Windows
└── assets/
    └── memes/           # Folder media meme (foto, video, file .txt)
```

## 🤝 Kontribusi
1. Fork repositori ini.
2. Buat branch baru (`git checkout -b fitur-baru`).
3. Commit perubahan (`git commit -m "Tambah fitur X"`).
4. Push ke branch (`git push origin fitur-baru`).
5. Buat Pull Request.

## 📜 Lisensi
Proyek ini dilisensikan di bawah MIT License.
