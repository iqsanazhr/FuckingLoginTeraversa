import os
from dotenv import load_dotenv

load_dotenv()

# Kredensial Bot Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Kunci Enkripsi Master (AES-256-GCM)
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "9f8a3c2e1b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f").strip()

# Database Config (Supabase Postgres atau SQLite lokal)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# Jika memakai direct PostgreSQL connection string dari Supabase:
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///attendance.db"

# Untuk kompatibilitas SQLAlchemy dengan postgresql:// bukan postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Akun testing lokal (opsional)
UNSOED_EMAIL = os.getenv("UNSOED_EMAIL", "").strip()
UNSOED_PASSWORD = os.getenv("UNSOED_PASSWORD", "").strip()
