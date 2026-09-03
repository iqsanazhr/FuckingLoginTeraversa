"""
Telegram Bot Handler for Teraversa UNSOED
Developer: nctreap_
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Watermark Developer
WATERMARK = "<i>dev: nctreap_</i>"

# State untuk ConversationHandler Login
EMAIL_STATE, PASSWORD_STATE = range(2)

# Temporary context cache untuk pending OTP per user
# user_id -> idjadwal
PENDING_OTP = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if user:
        text = (
            f"👋 Halo, <b>{user.full_name or 'Mahasiswa'}</b>!\n\n"
            f"Akun Anda terhubung dengan:\n"
            f"📧 <code>{user.email}</code>\n\n"
            f"<b>Fitur Bot:</b>\n"
            f"• /matkul - Lihat daftar mata kuliah & tombol presensi\n"
            f"• /refresh - Perbarui daftar mata kuliah dari Unsoed\n"
            f"• /status - Cek status akun Anda\n"
            f"• /logout - Putuskan kaitan akun\n\n"
            f"💡 <b>Cara Cepat Isi Presensi:</b>\n"
            f"Langsung ketik: <code>NAMAMATKUL [TOKEN]</code>\n"
            f"Contoh: <code>ERP 123456</code> atau <code>UPL 654321</code>\n\n"
            f"{WATERMARK}"
        )
        keyboard = [
            [InlineKeyboardButton("📚 Lihat Mata Kuliah", callback_data="btn_matkul")],
            [
                InlineKeyboardButton("🔄 Refresh Data", callback_data="btn_refresh"),
                InlineKeyboardButton("🚪 Logout Akun", callback_data="btn_logout_confirm"),
            ],
        ]
    else:
        text = (
            "👋 Selamat Datang di <b>Bot Auto Presensi Unsoed</b>!\n\n"
            "Bot ini membantu Anda melakukan presensi perkuliahan di Teraversa Unsoed langsung dari Telegram.\n\n"
            "🔒 <b>Keamanan Terjamin (Standar 2026):</b>\n"
            "Kredensial Anda dienkripsi menggunakan algoritma <b>AES-256-GCM</b> di database, dan pesan password akan segera dihapus otomatis dari chat.\n\n"
            "Silakan hubungkan akun Unsoed Anda dengan menekan tombol di bawah atau ketik /login."
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Sambungkan Akun Unsoed", callback_data="btn_login_start")]
        ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


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
        f"• Enkripsi: AES-256-GCM (Aktif)\n\n"
        f"{WATERMARK}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# --- Conversation Handler untuk Login ---
async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "📝 <b>Langkah 1/2:</b>\nSilakan ketik <b>Email akun Unsoed</b> Anda:\n(Contoh: <code>nama@mhs.unsoed.ac.id</code>)",
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
        "🔑 <b>Langkah 2/2:</b>\nSilakan ketik <b>Password akun Unsoed</b> Anda:\n\n"
        "<i>🛡️ Demi privasi, pesan password Anda akan segera kami hapus otomatis dari obrolan ini setelah diterima.</i>",
        parse_mode="HTML"
    )
    return PASSWORD_STATE


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    email = context.user_data.get("login_email")
    telegram_id = update.effective_user.id

    # Hapus pesan password demi privasi
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Gagal menghapus pesan password: {e}")

    progress_msg = await update.effective_chat.send_message("⏳ Sedang memverifikasi kredensial ke SSO Unsoed...")

    # Uji login
    client = UnsoedClient()
    success, full_name, err = client.login(email, password)

    if not success:
        await progress_msg.edit_text(
            f"❌ <b>Login Gagal!</b>\n{err}\n\nSilakan ketik /login untuk mengulangi.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # Simpan ke Database dengan AES-256-GCM
    db.save_user(telegram_id, email, password, full_name)

    # Ambil dan simpan daftar mata kuliah
    courses = client.get_courses()
    db.save_courses(telegram_id, courses)

    text = (
        f"✅ <b>Akun Berhasil Dihubungkan!</b>\n\n"
        f"Selamat datang, <b>{full_name}</b>!\n"
        f"Berhasil memuat <b>{len(courses)}</b> mata kuliah ke cache.\n\n"
        f"Gunakan /matkul untuk melihat jadwal & tombol presensi."
    )
    await progress_msg.edit_text(text, parse_mode="HTML")
    return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        # Coba fetch live jika cache kosong
        msg = await update.effective_message.reply_text("⏳ Mengambil data mata kuliah dari Teraversa...")
        client = UnsoedClient()
        success, _, _ = client.login(user.email, user.get_password())
        if success:
            courses_data = client.get_courses()
            db.save_courses(telegram_id, courses_data)
            courses = db.get_courses(telegram_id)
            await msg.delete()

    if not courses:
        await update.effective_message.reply_text("⚠️ Tidak ada mata kuliah aktif yang ditemukan di akun Anda.")
        return

    text = "📚 <b>Daftar Mata Kuliah Aktif:</b>\n\n"
    keyboard = []

    for idx, c in enumerate(courses, 1):
        alias = c.alias or "OTP"
        text += (
            f"<b>{idx}. {alias} - {c.course_name}</b>\n"
            f"   🗓️ {c.schedule_info or 'Jadwal belum ditentukan'}\n"
            f"   👉 Format cepat: <code>{alias} [TOKEN]</code>\n\n"
        )
        
        # Format tombol: "Presensi: {alias} - {nama lengkap matkul}"
        # Dipangkas jika terlalu panjang agar tidak terpotong jelek di UI Telegram
        clean_name = c.course_name
        if len(clean_name) > 30:
            clean_name = clean_name[:27] + "..."
        btn_label = f"Presensi: {alias} - {clean_name}"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data=f"otp_{c.idjadwal}")])

    keyboard.append([
        InlineKeyboardButton("🔄 Refresh Data", callback_data="btn_refresh"),
        InlineKeyboardButton("🚪 Logout Akun", callback_data="btn_logout_confirm"),
    ])

    text += (
        "💡 <i>Klik tombol mata kuliah di atas untuk input token, atau kirim langsung format cepat:</i>\n"
        "<code>KODEMATKUL [TOKEN]</code> (contoh: <code>KRIPTO 123456</code> atau <code>ERP 654321</code>)\n\n"
        f"{WATERMARK}"
    )

    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text("❌ Akun Anda belum terhubung. Ketik /login terlebih dahulu.")
        return

    msg = await update.effective_message.reply_text("⏳ Memperbarui daftar mata kuliah dari Teraversa...")
    client = UnsoedClient()
    success, full_name, err = client.login(user.email, user.get_password())

    if not success:
        await msg.edit_text(f"❌ Gagal login ke Unsoed saat refresh: {err}")
        return

    courses_data = client.get_courses()
    db.save_courses(telegram_id, courses_data)
    await msg.edit_text(f"✅ Berhasil memperbarui <b>{len(courses_data)}</b> mata kuliah!", parse_mode="HTML")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user:
        await update.effective_message.reply_text("ℹ️ Akun Anda belum terdaftar di sistem.")
        return

    confirm_keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Logout Sekarang", callback_data="btn_logout_execute"),
            InlineKeyboardButton("❌ Batal", callback_data="btn_logout_cancel"),
        ]
    ]
    await update.effective_message.reply_text(
        "⚠️ <b>Konfirmasi Logout</b>\n\n"
        "Apakah Anda yakin ingin memutuskan kaitan akun Unsoed?\n"
        "Seluruh data email, password terenkripsi, dan cache jadwal Anda akan dihapus permanen dari bot.",
        reply_markup=InlineKeyboardMarkup(confirm_keyboard),
        parse_mode="HTML"
    )


# --- Callback Query Handler ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    telegram_id = update.effective_user.id

    if data == "btn_matkul":
        await matkul_command(update, context)
    elif data == "btn_refresh":
        await refresh_command(update, context)
    elif data == "btn_login_start":
        await login_start(update, context)
    elif data == "btn_logout_confirm":
        confirm_keyboard = [
            [
                InlineKeyboardButton("✅ Ya, Logout Sekarang", callback_data="btn_logout_execute"),
                InlineKeyboardButton("❌ Batal", callback_data="btn_logout_cancel"),
            ]
        ]
        await query.message.reply_text(
            "⚠️ <b>Konfirmasi Logout</b>\n\n"
            "Apakah Anda yakin ingin memutuskan kaitan akun Unsoed?\n"
            "Seluruh data email, password terenkripsi, dan cache jadwal Anda akan dihapus permanen dari bot.",
            reply_markup=InlineKeyboardMarkup(confirm_keyboard),
            parse_mode="HTML"
        )
    elif data == "btn_logout_execute":
        db.delete_user(telegram_id)
        if telegram_id in PENDING_OTP:
            del PENDING_OTP[telegram_id]
        await query.message.edit_text(
            "✅ <b>Berhasil Logout!</b>\n\n"
            "Akun Unsoed Anda telah diputuskan dan seluruh kredensial telah dibersihkan dari database.\n\n"
            "Untuk menghubungkan kembali akun Anda di masa mendatang, silakan ketik /login.",
            parse_mode="HTML"
        )
    elif data == "btn_logout_cancel":
        await query.message.edit_text("👌 Logout dibatalkan.")
    elif data.startswith("otp_"):
        idjadwal = data.replace("otp_", "")
        # Cari info matkul
        course = db.find_course(telegram_id, idjadwal)
        cname = course.course_name if course else f"ID: {idjadwal}"
        
        # Set state pending OTP
        PENDING_OTP[telegram_id] = idjadwal
        
        await query.message.reply_text(
            f"✍️ <b>Input Token Presensi</b>\n"
            f"Mata Kuliah: <b>{cname}</b>\n\n"
            f"Silakan balas pesan ini dengan <b>6 digit angka token</b>:",
            parse_mode="HTML"
        )


# --- Text Message Handler (Presensi Langsung) ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    text = update.message.text.strip()
    user = db.get_user(telegram_id)

    if not user:
        return

    # Skenario 1: User sebelumnya mengklik tombol matkul dan sedang menunggu input token 6 digit
    if telegram_id in PENDING_OTP and re.match(r"^\d{6}$", text):
        idjadwal = PENDING_OTP.pop(telegram_id)
        course = db.find_course(telegram_id, idjadwal)
        cname = course.course_name if course else f"ID: {idjadwal}"
        await _process_attendance(update, user, idjadwal, cname, text)
        return

    # Skenario 2: Format langsung "NAMAMATKUL {token}" atau "KODE 123456"
    # Contoh: "ERP 123456", "UPL 654321", "228269 123456"
    parts = text.split()
    if len(parts) >= 2:
        token_candidate = parts[-1]
        matkul_candidate = " ".join(parts[:-1])

        if re.match(r"^\d{4,8}$", token_candidate):
            # Cari matkul berdasarkan nama/alias/idjadwal
            course = db.find_course(telegram_id, matkul_candidate)
            if course:
                await _process_attendance(update, user, course.idjadwal, course.course_name, token_candidate)
                return
            else:
                await update.message.reply_text(
                    f"⚠️ Mata kuliah dengan nama/kode <b>{matkul_candidate}</b> tidak ditemukan.\n"
                    f"Ketik /matkul untuk melihat daftar kode yang tersedia.",
                    parse_mode="HTML"
                )
                return


async def _process_attendance(update: Update, user, idjadwal: str, course_name: str, token: str):
    progress = await update.message.reply_text(
        f"⏳ Mengirim token <code>{token}</code> untuk <b>{course_name}</b> ke Teraversa...",
        parse_mode="HTML"
    )

    client = UnsoedClient()
    # Login dulu untuk mendapatkan session cookies aktif
    logged_in, _, err = client.login(user.email, user.get_password())
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
        },
        fallbacks=[CommandHandler("cancel", login_cancel)],
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(login_conv)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("matkul", matkul_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("unlink", logout_command))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app
