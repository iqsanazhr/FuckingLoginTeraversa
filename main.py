"""
Auto Presensi Teraversa UNSOED - Telegram Bot
Developer: nctreap_
"""

import os
import sys
import logging
from config import TELEGRAM_BOT_TOKEN, DATABASE_URL, UNSOED_EMAIL, UNSOED_PASSWORD
import database as db
from bot import build_application
from unsoed_client import UnsoedClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Main")

import socket

def acquire_single_instance_lock(port: int = 48291):
    """Mencegah bot berjalan ganda pada satu sistem"""
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.bind(("127.0.0.1", port))
        return lock_socket
    except socket.error:
        print("\n[!] PERINGATAN: Bot sudah berjalan di proses lain!")
        print("    Instance baru ini dihentikan agar tidak terjadi duplikasi pesan.\n")
        sys.exit(0)

def main():
    print("==================================================")
    print("       AUTO PRESENSI UNSOED - TELEGRAM BOT        ")
    print("==================================================")

    # Kunci single instance
    _lock = acquire_single_instance_lock()

    # 1. Inisialisasi Database (Supabase / SQLite)
    logger.info("Menginisialisasi tabel database...")
    db.init_db()

    # 2. Validasi Token Bot Telegram
    if not TELEGRAM_BOT_TOKEN:
        print("\n[!] PERINGATAN: TELEGRAM_BOT_TOKEN belum diset di .env")
        print("    Dapatkan token dari @BotFather di Telegram lalu isi di file .env")
        print("    Contoh: TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPqRstUvwxYZ\n")
        sys.exit(1)

    # 3. Build dan Run Telegram Bot
    logger.info("Membangun aplikasi bot Telegram...")
    app = build_application()

    logger.info("Bot siap berjalan (Polling mode)... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
