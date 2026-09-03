# TERAVERSA UNSOED AUTO ATTENDANCE BOT

**Automated Attendance & Token Submission System for Universitas Jenderal Soedirman (Teraversa Portal)**  
*(Informatics / Computer Science — Universitas Jenderal Soedirman)*

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![Security](https://img.shields.io/badge/Security-Zero--Knowledge_E2EE-16a34a?style=flat-square)](https://github.com/iqsanazhr/FuckingLoginTeraversa)
[![Platform](https://img.shields.io/badge/Platform-Telegram_Bot-2563eb?style=flat-square&logo=telegram&logoColor=white)](https://t.me/autoinputoken_bot)
[![Database](https://img.shields.io/badge/Database-Supabase_%7C_PostgreSQL-059669?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![Deployment](https://img.shields.io/badge/Deploy-Railway_%7C_Always--On-7c3aed?style=flat-square&logo=railway&logoColor=white)](https://railway.app)
[![Developer](https://img.shields.io/badge/dev-nctreap_-%23000?style=flat-square&logo=github)](https://github.com/iqsanazhr)

---

## 📖 Overview

**Teraversa Unsoed Auto Attendance Bot** is an intelligent server application and Telegram bot designed to automate the university lecture attendance process on the UNSOED Super App (**Teraversa** - `https://teraversa.unsoed.ac.id/mobile/otp`).

It enables students to submit 6-digit lecture attendance OTP tokens in real-time straight from Telegram via interactive inline buttons or quick text commands, eliminating the friction of manual multi-step web logins.

---

## 🚀 Key Features

- **SSO & OAuth2 Lifecycle Automation**: Handles the full university authentication chain—including `account.unsoed.ac.id` CSRF retrieval, credential verification, and OAuth 2.0 authorization callbacks to Teraversa.
- **Zero-Knowledge E2EE Security (4-Digit Personal PIN)**: Modeled after WhatsApp's client-side key isolation. Passwords are encrypted using keys derived from the user's **personal 4-digit PIN** via **PBKDF2-HMAC-SHA256 (100,000 iterations)** and **AES-256-GCM**. The server and database owners **cannot read student passwords**.
- **Chat Privacy & Ephemeral Memory**: Passwords and PINs entered in Telegram chats are **immediately auto-deleted** upon reception and only held in RAM for ~2 seconds during attendance execution.
- **Interactive & Quick-Input Modes**:
  - **One-Click Inline Keyboard**: Browse active courses via `/matkul` and click the corresponding course button to trigger token submission.
  - **Fast Command Syntax**: Directly message `COURSE_CODE {token} {pin}` (e.g., `ERP 123456 9988`) for instant processing.
  - **Computer Vision QR Code Scanning (BETA)**: Directly send or forward a photo of the lecture QR code displayed on the classroom projector. The bot auto-detects and decodes the QR hash using OpenCV and executes the attendance immediately.
  - **Comprehensive Attendance Audit (`/logpresensi`)**: View aggregated course attendance counts (e.g., 1/2 meetings) and drill down into per-meeting timestamps with 1-click interactive modal buttons.
- **Flexible Dual-Database Architecture**:
  - Cloud PostgreSQL on **Supabase** for persistent, scalable production deployment.
  - Automatic fallback to local **SQLite** (`attendance.db`) for rapid local development.
- **Single-Instance Mutex Lock**: Built-in socket binding ensures only one bot daemon process runs at a time, preventing duplicate responses and Telegram polling conflicts.

---

## 📋 Telegram Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Welcome screen, account status, and quick action buttons |
| `/login` or `/link` | Secure interactive login flow to link UNSOED student credentials |
| `/matkul` | View active registered courses with schedules and 1-click attendance buttons |
| `/qrpresensi` or `/qr` | Guide & direct submission for QR Code lecture attendance (BETA) |
| `/logpresensi` or `/rekap` | View attendance summary (e.g. 1/2 meetings) & inspect detailed meeting timestamps |
| `/refresh` | Synchronize course cache directly from the live UNSOED portal |
| `/status` | Check encryption health, student profile, and registered course count |
| `/logout` | Unlink account, purge credentials, and reset forgotten 4-digit PIN |
| `/bantuan` or `/help` | Comprehensive usage guide, fast syntax examples, and PIN reset guide |

---

## 📂 Project Structure

```text
autoinputoken/
│
├── .env.example          # Environment template for public repositories
├── .gitignore            # Git exclusion rules (protects .env and databases)
├── Procfile              # Railway worker process definition
├── README.md             # Project documentation (English)
├── requirements.txt      # Production Python dependencies
│
├── main.py               # Application entry point with single-instance lock
├── config.py             # Environment and secret configuration loader
├── bot.py                # Telegram bot conversation and callback handlers
├── database.py           # SQLAlchemy models (Users, Courses, AttendanceLogs)
├── security.py           # AES-256-GCM authenticated encryption engine
├── unsoed_client.py      # HTTP scraper engine for SSO, course parser, and OTP submitter
│
└── tests/                # Verification and endpoint research scripts
    ├── test_login.py
    ├── test_enterotp.py
    └── test_submit_otp.py
```

---

## 🛠️ Getting Started Locally

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/iqsanazhr/FuckingLoginTeraversa.git
cd FuckingLoginTeraversa
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy [.env.example](file:///d:/autoinputoken/.env.example) to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
```env
# Telegram Bot Token (obtain from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 32-byte Hex Master Key for AES-256-GCM
APP_SECRET_KEY=9f8a3c2e1b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f

# Database Connection (default: SQLite)
DATABASE_URL=sqlite:///attendance.db
```

### 3. Run the Bot
```bash
python main.py
```

---

## ☁️ Cloud Integration & Deployment

### Supabase Setup (PostgreSQL)
1. Navigate to the [Supabase Dashboard](https://supabase.com/dashboard) and create a project.
2. Go to **Project Settings** $\rightarrow$ **Database**.
3. Under **Connection String**, select **URI** (Transaction pooler or Session mode).
4. Update `DATABASE_URL` in your `.env` or cloud environment:
   ```env
   DATABASE_URL=postgresql://postgres.[REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
*(Database tables are automatically created on first startup).*

### Railway Deployment (24/7 Always-On)
1. Push this repository to your GitHub account.
2. Log in to [Railway.app](https://railway.app/) and select **New Project** $\rightarrow$ **Deploy from GitHub repo**.
3. In the Railway dashboard under **Variables**, set:
   - `TELEGRAM_BOT_TOKEN`
   - `APP_SECRET_KEY`
   - `DATABASE_URL`
4. Railway automatically detects the [Procfile](file:///d:/autoinputoken/Procfile) (`worker: python main.py`) and keeps your bot alive 24/7!

---

## 🔒 Security & Privacy Notice

- **Zero Cleartext Credentials**: Passwords stored in the database are protected with industry-standard **AES-256-GCM**.
- **Chat Privacy**: Credentials sent in Telegram messages during `/login` are automatically deleted immediately after processing.
- **Git Shield**: [.gitignore](file:///d:/autoinputoken/.gitignore) strictly prevents `.env`, secret tokens, and database files from ever being pushed to public version control.

---

## 📄 License
This project is built for educational, research, and personal workflow productivity purposes.

---

<p align="center">
  <sub>⚡ Developed by <b><a href="https://github.com/iqsanazhr">nctreap_</a></b></sub>
</p>
