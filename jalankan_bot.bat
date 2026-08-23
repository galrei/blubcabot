@echo off
title Menjalankan BlubcaBot
color 0A

:: Cek koneksi internet
ping -n 1 google.com >nul
if errorlevel 1 (
    echo Tidak ada koneksi internet! Pastikan Anda terhubung ke jaringan.
    pause
    exit
)

:: Aktifkan virtual environment
if exist venv (
    echo Mengaktifkan virtual environment...
    call venv\Scripts\activate
)

:: Jalankan bot
echo Menjalankan BlubcaBot...
python bot.py

:: Notifikasi jika bot berhenti
echo Bot berhenti. Tekan tombol apa saja untuk keluar...
pause
