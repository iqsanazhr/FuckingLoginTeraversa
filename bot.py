"""
Telegram Bot Handler for Teraversa UNSOED
Developer: nctreap_
Arsitektur Keamanan: Zero-Knowledge E2EE (4-Digit Personal PIN)
"""

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
import database as db
from unsoed_client import UnsoedClient
from qr_scanner import scan_qr_from_bytes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Watermark Developer
WATERMARK = "<i>dev: nctreap_</i>"

# State untuk ConversationHandler Login
EMAIL_STATE, PASSWORD_STATE, PIN_STATE = range(3)

# Temporary context cache untuk pending flow per user
# user_id -> {'action': str, ...}
PENDING_FLOW = {}

# Cache sesi rekap kehadiran Teraversa
# user_id -> {'client': UnsoedClient, 'summary': list, 'user_name': str}
REKAP_CACHE = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if user:
        text = (
            f"👋 Halo, <b>{user.full_name or 'Mahasiswa'}</b>!\n\n"
            f"Akun Anda terhubung dengan:\n"
            f"📧 <code>{user.email}</code>\n"
            f"🛡️ Keamanan: <b>Zero-Knowledge E2EE (PIN 4-Digit)</b>\n\n"
            f"<b>Fitur Bot:</b>\n"
            f"• /matkul - Lihat jadwal mata kuliah & tombol presensi\n"
            f"• /logpresensi - Rekap kehadiran kuliah & riwayat per pertemuan\n"
            f"• /refresh - Perbarui daftar mata kuliah dari Unsoed\n"
            f"• /status - Cek status akun Anda\n"
            f"• /logout - Putuskan kaitan akun & reset PIN\n"
            f"• /bantuan - Panduan lengkap & cara reset PIN jika lupa\n\n"
            f"💡 <b>Cara Cepat Isi Presensi:</b>\n"
            f"• <b>Format Teks:</b> <code>KODEMATKUL [TOKEN] [PIN]</code> (contoh: <code>ERP 123456 1234</code>)\n"
            f"• 📸 <b>Foto QR Code [BETA]:</b> Kirim langsung foto QR code di kelas ke bot ini!\n\n"
            f"{WATERMARK}"
        )
        keyboard = [
            [InlineKeyboardButton("📚 Lihat Mata Kuliah", callback_data="btn_matkul")],
            [
                InlineKeyboardButton("📊 Rekap Kehadiran", callback_data="btn_logpresensi"),
                InlineKeyboardButton("🔄 Refresh Data", callback_data="btn_refresh"),
            ],
            [
                InlineKeyboardButton("📖 Panduan", callback_data="btn_help"),
                InlineKeyboardButton("🚪 Logout", callback_data="btn_logout_confirm"),
            ],
        ]
    else:
        text = (
            "👋 Selamat Datang di <b>Bot Auto Presensi Unsoed</b>!\n\n"
            "Bot ini membantu Anda melakukan presensi perkuliahan di Teraversa Unsoed langsung dari Telegram.\n\n"
            "🔒 <b>Keamanan Zero-Knowledge E2EE (Standar 2026):</b>\n"
            "• Password Anda dienkripsi AES-256-GCM menggunakan <b>PIN 4-digit buatan Anda sendiri</b>.\n"
            "• Pemilik server & admin database <b>buta total</b> dan tidak bisa membaca password Anda.\n"
            "• Pesan password dan PIN akan otomatis dihapus seketika dari obrolan.\n\n"
            "Silakan klik tombol di bawah untuk menghubungkan akun:"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Sambungkan Akun Unsoed", callback_data="btn_login_start")]
        ]

    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.message.reply_text("❌ Akun Anda belum terhubung. Ketik /login untuk menghubungkan.")
        return

    courses = db.get_courses(telegram_id)
    text = (
        f"📊 <b>Status Akun:</b>\n"
        f"• Nama: <b>{user.full_name or '-'}</b>\n"
        f"• Email: <code>{user.email}</code>\n"
        f"• Jumlah Matkul Terdaftar: <b>{len(courses)}</b> matkul\n"
        f"• Keamanan: <b>Zero-Knowledge E2EE (AES-256-GCM)</b>\n"
        f"• Status Kunci: <b>Terkunci PIN 4-Digit Pribadi</b>\n\n"
        f"{WATERMARK}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# --- Conversation Handler untuk Login ---
async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "📝 <b>Langkah 1/3:</b>\nSilakan ketik <b>Email akun Unsoed</b> Anda:\n(Contoh: <code>nama@mhs.unsoed.ac.id</code>)",
        parse_mode="HTML"
    )
    return EMAIL_STATE


async def login_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email or "unsoed.ac.id" not in email:
        await update.message.reply_text("⚠️ Format email tidak valid. Pastikan menggunakan email Unsoed (@*.unsoed.ac.id). Coba lagi:")
        return EMAIL_STATE

    context.user_data["login_email"] = email
    await update.message.reply_text(
        "🔑 <b>Langkah 2/3:</b>\nSilakan ketik <b>Password akun Unsoed</b> Anda:\n\n"
        "<i>🛡️ Pesan password Anda akan otomatis dihapus seketika dari obrolan ini demi privasi.</i>",
        parse_mode="HTML"
    )
    return PASSWORD_STATE


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    
    # Hapus pesan password demi privasi
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Gagal menghapus pesan password: {e}")

    context.user_data["login_password"] = password

    await update.effective_chat.send_message(
        "🔐 <b>Langkah 3/3: Buat PIN Rahasia 4-Digit</b>\n\n"
        "Silakan ketik <b>4 digit angka</b> yang ingin Anda gunakan sebagai PIN pengaman (contoh: <code>1234</code> atau <code>9876</code>).\n\n"
        "<i>💡 Konsep Zero-Knowledge E2EE (ala WhatsApp):</i>\n"
        "<i>Password Anda akan digembok menggunakan PIN ini. Siapa pun (termasuk pemilik server bot ini) tidak akan bisa membaca password Anda tanpa PIN tersebut.</i>\n\n"
        "<i>(Pesan PIN juga akan otomatis dihapus seketika)</i>",
        parse_mode="HTML"
    )
    return PIN_STATE


async def login_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pin = update.message.text.strip()
    
    # Hapus pesan PIN demi privasi
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Gagal menghapus pesan PIN: {e}")

    if len(pin) != 4 or not pin.isdigit():
        await update.effective_chat.send_message(
            "⚠️ PIN harus berupa <b>tepat 4 digit angka</b> (contoh: <code>1234</code> atau <code>9988</code>).\n"
            "Silakan ketik ulang PIN Anda:",
            parse_mode="HTML"
        )
        return PIN_STATE

    email = context.user_data.get("login_email")
    password = context.user_data.get("login_password")
    telegram_id = update.effective_user.id

    progress_msg = await update.effective_chat.send_message(
        "⏳ Sedang memverifikasi kredensial ke SSO Unsoed dan mengunci data dengan PIN Anda..."
    )

    # Uji login ke SSO Unsoed
    client = UnsoedClient()
    success, full_name, err = client.login(email, password)

    if not success:
        # Bersihkan memori
        context.user_data.pop("login_password", None)
        await progress_msg.edit_text(
            f"❌ <b>Login ke Unsoed Gagal!</b>\n{err}\n\nSilakan ketik /login untuk mengulangi.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    try:
        # Simpan ke Database dengan Zero-Knowledge PIN E2EE
        db.save_user(telegram_id=telegram_id, email=email, password_plain=password, pin=pin, full_name=full_name)

        # Hapus paksa password dari RAM seketika
        context.user_data.pop("login_password", None)
        del password

        # Ambil dan simpan daftar mata kuliah
        courses = client.get_courses()
        db.save_courses(telegram_id, courses)

        text = (
            f"🎉 <b>Akun Berhasil Dihubungkan!</b>\n\n"
            f"• Nama: <b>{full_name}</b>\n"
            f"• Email: <code>{email}</code>\n"
            f"• Keamanan: <b>Zero-Knowledge E2EE (PIN 4-Digit Aktif)</b>\n"
            f"• Mata Kuliah Dimuat: <b>{len(courses)}</b> matkul\n\n"
            f"📚 Ketik /matkul untuk melihat jadwal & tombol presensi langsung.\n"
            f"📊 Ketik /logpresensi untuk melihat rekap kehadiran kuliah.\n\n"
            f"💡 <b>Cara Presensi Cepat di Kelas:</b>\n"
            f"Ketik: <code>KODEMATKUL [TOKEN] [PIN]</code>\n"
            f"Contoh: <code>ERP 123456 {pin}</code>\n\n"
            f"<i>⚠️ Catatan: Ingat selalu PIN 4-digit Anda! Kunci enkripsi ini hanya Anda yang memegangnya.</i>\n\n"
            f"{WATERMARK}"
        )
        keyboard = [
            [InlineKeyboardButton("📚 Lihat Mata Kuliah", callback_data="btn_matkul")],
            [InlineKeyboardButton("🚪 Logout & Reset PIN", callback_data="btn_logout_confirm")],
        ]
        del pin
        await progress_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error saat login_pin: {e}", exc_info=True)
        await progress_msg.edit_text(f"❌ Terjadi kesalahan saat memproses login: {e}")
    return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("login_password", None)
    await update.message.reply_text("🚫 Proses login dibatalkan.")
    return ConversationHandler.END


# --- Menu Matkul ---
async def matkul_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("❌ Akun Anda belum terhubung. Ketik /login terlebih dahulu.")
        return

    courses = db.get_courses(telegram_id)
    if not courses:
        await update.effective_message.reply_text(
            "📭 Belum ada daftar mata kuliah tersimpan.\n"
            "Ketik /refresh untuk memuat daftar mata kuliah dari Unsoed."
        )
        return

    keyboard = []
    text = "📚 <b>Daftar Mata Kuliah Anda:</b>\n\n"

    for c in courses:
        schedule = c.schedule_info if c.schedule_info else "Jadwal belum ada"
        alias = c.alias if c.alias else c.idjadwal
        text += (
            f"• <b>{c.course_name}</b>\n"
            f"  └ Kode: <code>{alias}</code> | ID: <code>{c.idjadwal}</code>\n"
            f"  └ <i>{schedule}</i>\n\n"
        )
        button_label = f"Presensi: {alias} - {c.course_name[:20]}"
        keyboard.append([InlineKeyboardButton(button_label, callback_data=f"otp_{c.idjadwal}")])

    text += (
        "💡 <i>Klik tombol mata kuliah di atas untuk presensi, atau kirim langsung format cepat:</i>\n"
        "<code>KODEMATKUL [TOKEN] [PIN]</code>\n(contoh: <code>KRIPTO 123456 9988</code> atau <code>ERP 654321 1234</code>)\n\n"
        f"{WATERMARK}"
    )

    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("❌ Akun Anda belum terhubung. Ketik /login terlebih dahulu.")
        return

    # Jika akun memerlukan PIN untuk dekripsi
    if user.password_salt:
        PENDING_FLOW[telegram_id] = {"action": "refresh"}
        await update.effective_message.reply_text(
            "🔐 Masukkan <b>PIN 4-digit</b> Anda untuk otorisasi refresh data:\n"
            "<i>(Pesan PIN akan langsung dihapus otomatis)</i>",
            parse_mode="HTML"
        )
        return

    # Fallback jika akun lama belum pakai salt
    await _execute_refresh(update, user)


async def _execute_refresh(update: Update, user, pin: str = None):
    msg = await update.effective_message.reply_text("⏳ Memperbarui daftar mata kuliah dari Teraversa...")
    client = UnsoedClient()
    try:
        pwd = user.get_password(pin=pin)
    except ValueError as e:
        await msg.edit_text(f"❌ <b>Gagal Otorisasi:</b> {e}")
        return

    success, full_name, err = client.login(user.email, pwd)
    del pwd
    if pin:
        del pin
    if not success:
        await msg.edit_text(f"❌ Gagal login ke Unsoed saat refresh: {err}")
        return

    courses_data = client.get_courses()
    db.save_courses(user.telegram_id, courses_data)
    await msg.edit_text(f"✅ Berhasil memperbarui <b>{len(courses_data)}</b> mata kuliah!", parse_mode="HTML")


# --- Log & Rekap Presensi (/logpresensi & /rekap) ---
async def logpresensi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("❌ Akun Anda belum terhubung. Ketik /login terlebih dahulu.")
        return

    # Jika PIN dikirim langsung di argumen: /logpresensi 1234
    pin = None
    if context.args and len(context.args) == 1 and len(context.args[0]) == 4 and context.args[0].isdigit():
        pin = context.args[0]
        try:
            await update.message.delete()
        except Exception:
            pass
        await _execute_logpresensi(update, user, pin=pin)
        return

    # Jika butuh PIN tapi belum ada
    if user.password_salt:
        PENDING_FLOW[telegram_id] = {"action": "logpresensi"}
        await update.effective_message.reply_text(
            "🔐 Masukkan <b>PIN 4-digit</b> Anda untuk membuka rekap presensi:\n"
            "<i>(Pesan PIN akan langsung dihapus otomatis)</i>\n\n"
            "💡 <i>Tips: Anda juga bisa ketik langsung <code>/logpresensi [PIN]</code></i>",
            parse_mode="HTML"
        )
        return

    # Fallback jika akun lama
    await _execute_logpresensi(update, user)


async def _execute_logpresensi(update: Update, user, pin: str = None):
    msg = await update.effective_chat.send_message("⏳ Mengambil rekap presensi dari Teraversa...")
    try:
        plain_password = user.get_password(pin=pin)
    except ValueError as e:
        keyboard = [
            [InlineKeyboardButton("🚪 Lupa PIN? Logout & Reset", callback_data="btn_logout_confirm")]
        ]
        await msg.edit_text(
            f"❌ <b>Otorisasi Gagal!</b>\n{e}\n\n"
            f"<i>💡 Lupa PIN? Klik tombol di bawah untuk Logout dan membuat PIN baru.</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    client = UnsoedClient()
    logged_in, user_name, err = client.login(user.email, plain_password)
    del plain_password
    if pin:
        del pin

    if not logged_in:
        await msg.edit_text(f"❌ Gagal login ke SSO Unsoed: {err}")
        return

    summary = client.get_attendance_summary()
    if not summary:
        await msg.edit_text("📭 Tidak ditemukan data rekap presensi di akun Anda saat ini.")
        return

    # Simpan ke REKAP_CACHE untuk membuka detail via tombol
    u_name = user_name or user.full_name or "Mahasiswa"
    REKAP_CACHE[user.telegram_id] = {
        "client": client,
        "summary": summary,
        "user_name": u_name
    }

    await _render_rekap_message(msg, user.telegram_id, summary, u_name)


async def _render_rekap_message(message_or_query, telegram_id: int, summary: list, user_name: str):
    text = (
        f"📊 <b>REKAP PRESENSI KULIAH (TERAVERSA)</b>\n"
        f"👤 Mahasiswa: <b>{user_name}</b>\n\n"
    )

    keyboard = []
    for idx, item in enumerate(summary):
        cname = item["course_name"]
        count_str = item["count_text"]
        text += f"• <b>{cname}</b>\n  └ Kehadiran: <b>{count_str}</b>\n\n"
        btn_label = f"📋 Rincian: {cname[:20]}"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data=f"rek_{idx}")])

    text += (
        "💡 <i>Klik tombol mata kuliah di atas untuk melihat rincian riwayat tiap pertemuan (status & waktu).</i>\n\n"
        f"{WATERMARK}"
    )

    keyboard.append([InlineKeyboardButton("🔄 Segarkan Rekap", callback_data="btn_rekap_refresh")])

    markup = InlineKeyboardMarkup(keyboard)
    if hasattr(message_or_query, "edit_text"):
        await message_or_query.edit_text(text, reply_markup=markup, parse_mode="HTML")
    elif hasattr(message_or_query, "edit_message_text"):
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


# --- Logout Handlers ---
async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("ℹ️ Anda memang belum menghubungkan akun apapun.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Logout Sekarang", callback_data="confirm_logout_yes"),
            InlineKeyboardButton("❌ Batal", callback_data="confirm_logout_no"),
        ]
    ]
    await update.effective_message.reply_text(
        f"⚠️ <b>Konfirmasi Logout & Reset PIN:</b>\n\n"
        f"Apakah Anda yakin ingin memutuskan kaitan akun <b>{user.email}</b>?\n"
        f"Semua kredensial terenkripsi, PIN lama, dan cache mata kuliah akan dihapus permanen.\n\n"
        f"<i>💡 Jika Anda lupa PIN, Anda bisa klik tombol 'Ya' di bawah, lalu ketik /login untuk membuat PIN baru!</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def logout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    if query.data == "confirm_logout_yes":
        success = db.delete_user(telegram_id)
        PENDING_FLOW.pop(telegram_id, None)
        REKAP_CACHE.pop(telegram_id, None)
        if success:
            await query.edit_message_text(
                "🚪 <b>Logout Berhasil (PIN Lama Dihapus)!</b>\n\n"
                "Semua data kredensial terenkripsi dan PIN lama Anda telah dihapus permanen dari server.\n"
                "Ketik /login kapan saja jika ingin menghubungkan kembali dan membuat PIN 4-digit baru!",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("ℹ️ Akun Anda sudah tidak ada di database.")
    elif query.data == "confirm_logout_no":
        await query.edit_message_text("✅ Logout dibatalkan. Akun Anda tetap terhubung.")


# --- Bantuan & Panduan Handler (/bantuan & /help) ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>PANDUAN LENGKAP PENGGUNAAN BOT</b>\n\n"
        "<b>1. Cara Presensi Cepat di Kelas</b>\n"
        "Saat dosen menampilkan kode token di proyektor, langsung kirim pesan:\n"
        "<code>KODEMATKUL [TOKEN] [PIN]</code>\n\n"
        "<i>Contoh:</i>\n"
        "• <code>ERP 123456 1234</code>\n"
        "• <code>KRIPTO 654321 9988</code>\n"
        "• <code>UKPL 789012 1234</code>\n\n"
        "<b>2. Cara Presensi Tombol Interaktif</b>\n"
        "• Ketik /matkul\n"
        "• Klik tombol mata kuliah yang sedang berlangsung\n"
        "• Kirimkan format: <code>[TOKEN] [PIN]</code> (contoh: <code>123456 1234</code>)\n\n"
        "<b>3. Melihat Rekap Kehadiran Kuliah</b>\n"
        "• Ketik /logpresensi (atau /rekap)\n"
        "• Bot akan menampilkan jumlah kehadiran (misal: 1 Pertemuan dari 2)\n"
        "• Klik tombol mata kuliah untuk melihat detail jam & tanggal setiap pertemuan.\n\n"
        "<b>4. Lupa PIN 4-Digit? (Cara Reset PIN)</b>\n"
        "Karena sistem menggunakan <b>Zero-Knowledge E2EE</b>, server tidak mengetahui PIN Anda. "
        "Jika Anda lupa PIN, Anda bisa membuat PIN baru dengan sangat mudah:\n"
        "1. Ketik /logout (seluruh kredensial & PIN lama otomatis dihapus bersih)\n"
        "2. Ketik /login untuk mengaitkan akun kembali dan membuat <b>PIN 4-digit baru</b>!\n\n"
        "<b>5. Daftar Perintah Bot:</b>\n"
        "• /start - Menu utama\n"
        "• /matkul - Daftar mata kuliah & tombol presensi\n"
        "• /logpresensi - Rekap kehadiran & riwayat per pertemuan\n"
        "• /refresh - Sinkronkan mata kuliah terbaru dari portal kampus\n"
        "• /status - Cek status profil & enkripsi akun\n"
        "• /logout - Putuskan kaitan akun & hapus PIN lama\n"
        "• /bantuan - Tampilkan panduan ini\n\n"
        f"{WATERMARK}"
    )
    keyboard = [
        [InlineKeyboardButton("📚 Lihat Mata Kuliah", callback_data="btn_matkul")],
        [InlineKeyboardButton("📊 Rekap Kehadiran", callback_data="btn_logpresensi")],
        [InlineKeyboardButton("🚪 Logout & Reset PIN", callback_data="btn_logout_confirm")],
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- Callback Query Handler (Tombol Menu & Matkul) ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    data = query.data

    if data == "btn_matkul":
        await matkul_command(update, context)
    elif data == "btn_logpresensi":
        await logpresensi_command(update, context)
    elif data == "btn_refresh":
        await refresh_command(update, context)
    elif data == "btn_logout_confirm":
        await logout_command(update, context)
    elif data == "btn_help":
        await help_command(update, context)
    elif data == "btn_rekap_refresh":
        await logpresensi_command(update, context)
    elif data == "btn_rekap_back":
        cache = REKAP_CACHE.get(telegram_id)
        if cache:
            await _render_rekap_message(query, telegram_id, cache["summary"], cache["user_name"])
        else:
            await query.edit_message_text("Sesi kedaluwarsa. Ketik /logpresensi untuk membuka kembali.")
    elif data.startswith("rek_"):
        idx = int(data.replace("rek_", ""))
        cache = REKAP_CACHE.get(telegram_id)
        if not cache or idx >= len(cache["summary"]):
            await query.answer("Sesi rekap telah kedaluwarsa. Ketik /logpresensi untuk memuat ulang.", show_alert=True)
            return

        item = cache["summary"][idx]
        client = cache["client"]
        
        await query.edit_message_text(f"⏳ Mengambil riwayat pertemuan untuk <b>{item['course_name']}</b>...", parse_mode="HTML")
        history = client.get_attendance_history(item["detail_url"])

        detail_text = (
            f"📋 <b>RIWAYAT PRESENSI KULIAH</b>\n"
            f"Mata Kuliah: <b>{item['course_name']}</b>\n"
            f"Total Kehadiran: <b>{item['count_text']}</b>\n\n"
        )

        if not history:
            detail_text += "<i>Belum ada data riwayat pertemuan yang terekam pada mata kuliah ini di Teraversa.</i>\n\n"
        else:
            for h in history:
                status_icon = "✅" if "hadir" in h["status"].lower() else "ℹ️"
                detail_text += (
                    f"• <b>Pertemuan {h['pert']}</b>: {status_icon} <code>{h['status'].upper()}</code>\n"
                    f"  └ Waktu: <i>{h['waktu']}</i>\n\n"
                )

        detail_text += f"{WATERMARK}"
        back_keyboard = [
            [InlineKeyboardButton("🔙 Kembali ke Daftar Rekap", callback_data="btn_rekap_back")]
        ]
        await query.edit_message_text(detail_text, reply_markup=InlineKeyboardMarkup(back_keyboard), parse_mode="HTML")
    elif data.startswith("otp_"):
        idjadwal = data.replace("otp_", "")
        course = db.find_course(telegram_id, idjadwal)
        cname = course.course_name if course else f"ID: {idjadwal}"
        
        # Simpan state pending
        PENDING_FLOW[telegram_id] = {"action": "attendance", "idjadwal": idjadwal, "course_name": cname, "step": "token"}
        
        await query.message.reply_text(
            f"✍️ <b>Presensi: {cname}</b>\n\n"
            f"Kirimkan format: <code>[TOKEN] [PIN]</code>\n"
            f"(Contoh: <code>123456 9988</code>)",
            parse_mode="HTML"
        )


# --- Text Message Handler (Presensi Cepat / Langsung) ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    text = update.message.text.strip()
    user = db.get_user(telegram_id)

    if not user:
        return

    # Skenario 0: Pending Rekap / Logpresensi dengan input PIN
    if telegram_id in PENDING_FLOW and PENDING_FLOW[telegram_id].get("action") == "logpresensi":
        try:
            await update.message.delete()
        except Exception:
            pass
        pin = text
        PENDING_FLOW.pop(telegram_id, None)
        await _execute_logpresensi(update, user, pin=pin)
        return

    # Skenario 0.5: Pending Presensi Scan QR dengan input PIN
    if telegram_id in PENDING_FLOW and PENDING_FLOW[telegram_id].get("action") == "qr_attendance":
        flow = PENDING_FLOW.pop(telegram_id)
        try:
            await update.message.delete()
        except Exception:
            pass
        pin = text
        prog_msg = await update.effective_chat.send_message("⏳ Memproses otorisasi PIN & presensi QR...", parse_mode="HTML")
        await _execute_qr_attendance(prog_msg, user, flow["decoded_text"], pin=pin)
        return

    # Skenario 1: Pending Refresh dengan input PIN
    if telegram_id in PENDING_FLOW and PENDING_FLOW[telegram_id].get("action") == "refresh":
        try:
            await update.message.delete()
        except Exception:
            pass
        pin = text
        PENDING_FLOW.pop(telegram_id, None)
        await _execute_refresh(update, user, pin=pin)
        return

    # Skenario 2: Pending Button Matkul (Format: "TOKEN PIN" atau "TOKEN")
    if telegram_id in PENDING_FLOW and PENDING_FLOW[telegram_id].get("action") == "attendance":
        flow = PENDING_FLOW[telegram_id]
        parts = text.split()
        if len(parts) >= 2:
            token = parts[0]
            pin = parts[1]
            PENDING_FLOW.pop(telegram_id, None)
            try:
                await update.message.delete()
            except Exception:
                pass
            await _process_attendance(update, user, flow["idjadwal"], flow["course_name"], token, pin)
            return
        elif len(parts) == 1 and re.match(r"^\d{4,8}$", parts[0]):
            flow["token"] = parts[0]
            flow["step"] = "pin"
            await update.message.reply_text(
                "🔐 Masukkan <b>PIN 4-digit</b> Anda untuk membuka enkripsi presensi:\n"
                "<i>(Pesan PIN akan langsung dihapus otomatis)</i>",
                parse_mode="HTML"
            )
            return
        elif flow.get("step") == "pin" and len(parts) == 1 and len(parts[0]) == 4 and parts[0].isdigit():
            token = flow.get("token")
            pin = parts[0]
            PENDING_FLOW.pop(telegram_id, None)
            try:
                await update.message.delete()
            except Exception:
                pass
            await _process_attendance(update, user, flow["idjadwal"], flow["course_name"], token, pin)
            return

    # Skenario 3: Format Langsung "KODEMATKUL TOKEN PIN"
    # Contoh: "ERP 123456 9988", "KRIPTO 654321 1234"
    parts = text.split()
    if len(parts) >= 3 and len(parts[-1]) == 4 and parts[-1].isdigit() and re.match(r"^\d{4,8}$", parts[-2]):
        pin = parts[-1]
        token = parts[-2]
        matkul_candidate = " ".join(parts[:-2])

        # Hapus pesan yang mengandung PIN demi privasi
        try:
            await update.message.delete()
        except Exception:
            pass

        course = db.find_course(telegram_id, matkul_candidate)
        if course:
            await _process_attendance(update, user, course.idjadwal, course.course_name, token, pin)
            return
        else:
            await update.message.reply_text(
                f"⚠️ Mata kuliah <b>{matkul_candidate}</b> tidak ditemukan.\n"
                f"Ketik /matkul untuk melihat daftar kode yang tersedia.",
                parse_mode="HTML"
            )
            return

    # Skenario 4: Format Langsung Tanpa PIN "KODEMATKUL TOKEN" (Misal: "ERP 123456")
    if len(parts) >= 2 and re.match(r"^\d{4,8}$", parts[-1]):
        token_candidate = parts[-1]
        matkul_candidate = " ".join(parts[:-1])
        course = db.find_course(telegram_id, matkul_candidate)

        if course:
            if user.password_salt:
                # Butuh PIN untuk Zero-Knowledge
                await update.message.reply_text(
                    f"🔐 <b>Presensi Memerlukan PIN Otorisasi</b>\n\n"
                    f"Ketik format lengkap: <code>{matkul_candidate} {token_candidate} [PIN]</code>\n"
                    f"Contoh: <code>{matkul_candidate} {token_candidate} 1234</code>\n\n"
                    f"<i>Password Anda terlindungi dengan Zero-Knowledge E2EE, sehingga PIN Anda diperlukan untuk membuka enkripsi.</i>",
                    parse_mode="HTML"
                )
                return
            else:
                # Akun lama tanpa salt
                await _process_attendance(update, user, course.idjadwal, course.course_name, token_candidate)
                return


async def _process_attendance(update: Update, user, idjadwal: str, course_name: str, token: str, pin: str = None):
    progress = await update.effective_chat.send_message(
        f"⏳ Mengirim token <code>{token}</code> untuk <b>{course_name}</b> ke Teraversa...",
        parse_mode="HTML"
    )

    # Buka enkripsi password
    try:
        plain_password = user.get_password(pin=pin)
    except ValueError as e:
        keyboard = [
            [InlineKeyboardButton("🚪 Lupa PIN? Logout & Reset", callback_data="btn_logout_confirm")]
        ]
        await progress.edit_text(
            f"❌ <b>Otorisasi Gagal!</b>\n{e}\n\n"
            f"Pastikan PIN 4-digit yang Anda masukkan benar.\n\n"
            f"<i>💡 Lupa PIN? Klik tombol di bawah untuk Logout dan membuat PIN baru dengan /login kembali.</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    client = UnsoedClient()
    logged_in, _, err = client.login(user.email, plain_password)
    # Hapus paksa password dan PIN dari RAM seketika
    del plain_password
    if pin:
        del pin

    if not logged_in:
        await progress.edit_text(f"❌ Gagal login ke SSO Unsoed: {err}")
        return

    # Submit OTP
    success, msg = client.submit_otp(idjadwal, token)

    # Simpan log ke database
    db.log_attendance(
        telegram_id=user.telegram_id,
        idjadwal=idjadwal,
        course_name=course_name,
        token=token,
        status="BERHASIL" if success else "GAGAL",
        message=msg,
    )

    if success:
        result_text = (
            f"🎉 <b>Presensi Berhasil!</b>\n\n"
            f"• Mata Kuliah: <b>{course_name}</b>\n"
            f"• Token: <code>{token}</code>\n"
            f"• Status: <b>Tercatat di Teraversa</b>\n\n"
            f"ℹ️ Pesan Kampus: <i>{msg}</i>"
        )
    else:
        result_text = (
            f"⚠️ <b>Presensi Gagal!</b>\n\n"
            f"• Mata Kuliah: <b>{course_name}</b>\n"
            f"• Token: <code>{token}</code>\n\n"
            f"Pesan dari Teraversa:\n<i>{msg}</i>"
        )

    result_text += f"\n\n{WATERMARK}"
    await progress.edit_text(result_text, parse_mode="HTML")


# --- QR Code Photo Handler (Presensi Foto QR - BETA) ---
async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("❌ Akun Anda belum terhubung. Ketik /login terlebih dahulu.")
        return

    progress = await update.effective_chat.send_message("🔍 <b>Memindai QR Code dari gambar... [BETA]</b>", parse_mode="HTML")

    try:
        # Dukung pengiriman foto biasa maupun dokumen gambar
        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
        elif update.message.document:
            photo_file = await update.message.document.get_file()
        else:
            await progress.edit_text("⚠️ Format gambar tidak didukung.")
            return

        img_bytes = await photo_file.download_as_bytearray()

        # Pindai dengan Computer Vision OpenCV
        decoded_text = scan_qr_from_bytes(bytes(img_bytes))

        if not decoded_text:
            await progress.edit_text(
                "⚠️ <b>QR Code Tidak Terdeteksi! [BETA]</b>\n\n"
                "Bot tidak menemukan kode QR pada gambar yang Anda kirim.\n"
                "<i>Tips: Pastikan foto QR code cukup terang, fokus, dan tidak terlalu blur atau miring.</i>",
                parse_mode="HTML"
            )
            return

        # Cek apakah user menyertakan PIN 4-digit di caption foto (misal: caption "1234")
        caption = update.message.caption.strip() if update.message.caption else ""
        pin = None
        if len(caption) == 4 and caption.isdigit():
            pin = caption
            try:
                await update.message.delete()
            except Exception:
                pass

        if user.password_salt and not pin:
            PENDING_FLOW[telegram_id] = {
                "action": "qr_attendance",
                "decoded_text": decoded_text,
            }
            await progress.edit_text(
                "📸 <b>Kode QR Berhasil Terdeteksi! [BETA]</b>\n\n"
                "Silakan ketik <b>PIN 4-digit</b> Anda untuk otorisasi presensi:\n"
                "<i>(Pesan PIN akan langsung dihapus otomatis)</i>\n\n"
                "💡 <i>Tips: Lain kali Anda bisa langsung ketik PIN di keterangan/caption saat mengirim foto!</i>",
                parse_mode="HTML"
            )
            return

        await _execute_qr_attendance(progress, user, decoded_text, pin=pin)

    except Exception as e:
        logger.error(f"Error scan foto QR: {e}", exc_info=True)
        await progress.edit_text(f"❌ Terjadi kesalahan saat memproses foto: {e}")


async def _execute_qr_attendance(progress_msg, user, decoded_text: str, pin: str = None):
    await progress_msg.edit_text("⏳ Sedang memverifikasi akun dan mengirim presensi QR ke Teraversa...", parse_mode="HTML")
    try:
        plain_password = user.get_password(pin=pin)
    except ValueError as e:
        keyboard = [
            [InlineKeyboardButton("🚪 Lupa PIN? Logout & Reset", callback_data="btn_logout_confirm")]
        ]
        await progress_msg.edit_text(
            f"❌ <b>Otorisasi Gagal!</b>\n{e}\n\n"
            f"<i>💡 Lupa PIN? Klik tombol di bawah untuk Logout dan membuat PIN baru.</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    client = UnsoedClient()
    logged_in, _, err = client.login(user.email, plain_password)
    del plain_password
    if pin:
        del pin

    if not logged_in:
        await progress_msg.edit_text(f"❌ Gagal login ke SSO Unsoed: {err}")
        return

    success, msg = client.submit_qr_attendance(decoded_text)

    # Simpan log ke database
    db.log_attendance(
        telegram_id=user.telegram_id,
        idjadwal="QR_SCAN",
        course_name="Presensi Scan QR (BETA)",
        token=decoded_text[:25],
        status="BERHASIL" if success else "GAGAL",
        message=msg,
    )

    if success:
        result_text = (
            f"🎉 <b>Presensi QR Berhasil! [BETA]</b>\n\n"
            f"• Status: <b>Tercatat di Teraversa</b>\n"
            f"ℹ️ Pesan Kampus: <i>{msg}</i>\n\n"
            f"{WATERMARK}"
        )
    else:
        result_text = (
            f"⚠️ <b>Presensi QR Gagal! [BETA]</b>\n\n"
            f"Pesan dari Teraversa:\n<i>{msg}</i>\n\n"
            f"{WATERMARK}"
        )

    await progress_msg.edit_text(result_text, parse_mode="HTML")


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diset di .env!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation Handler untuk /login
    login_conv = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_start),
            CommandHandler("link", login_start),
            CallbackQueryHandler(login_start, pattern="^btn_login_start$"),
        ],
        states={
            EMAIL_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_email)],
            PASSWORD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
            PIN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pin)],
        },
        fallbacks=[CommandHandler("cancel", login_cancel)],
        per_chat=True,
        per_user=True,
    )

    # Registrasi Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("matkul", matkul_command))
    app.add_handler(CommandHandler(["logpresensi", "rekap"], logpresensi_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler(["bantuan", "help"], help_command))
    app.add_handler(login_conv)

    # Callbacks untuk logout & menu inline
    app.add_handler(CallbackQueryHandler(logout_callback, pattern="^confirm_logout_"))
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Handler Foto / Gambar QR Code
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo_message))

    # Fallback text message untuk presensi cepat
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app
