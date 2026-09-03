import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("UNSOED_EMAIL")
PASSWORD = os.getenv("UNSOED_PASSWORD")

if not EMAIL or not PASSWORD:
    print("[ERROR] Email atau Password belum diset di .env")
    exit(1)

print(f"[*] Menyiapkan session untuk email: {EMAIL}")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
})

# Step 1: Mulai dari Teraversa Redirect
redirect_entry = "https://teraversa.unsoed.ac.id/auth/unsoed/redirect"
print(f"\n[1] Mengakses endpoint login Teraversa: {redirect_entry}")
resp = session.get(redirect_entry, allow_redirects=True)
print(f"    -> Status: {resp.status_code}")
print(f"    -> URL saat ini: {resp.url}")

# Step 2: Periksa apakah diarahkan ke halaman login account.unsoed.ac.id
soup = BeautifulSoup(resp.text, "html.parser")
csrf_input = soup.find("input", {"name": "_token"})

if not csrf_input:
    print("[!] Form login token CSRF tidak ditemukan langsung di halaman ini.")
    print("    Mencoba langsung ke https://account.unsoed.ac.id/login...")
    resp = session.get("https://account.unsoed.ac.id/login")
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "_token"})

if not csrf_input:
    print("[ERROR] Gagal menemukan CSRF token pada halaman login.")
    exit(1)

csrf_token = csrf_input.get("value")
print(f"[2] Berhasil mendapatkan CSRF token: {csrf_token[:10]}...")

# Step 3: Kirim POST Login
login_url = "https://account.unsoed.ac.id/login"
payload = {
    "_token": csrf_token,
    "login": EMAIL,
    "password": PASSWORD,
}

print(f"\n[3] Mengirim kredensial login ke {login_url}...")
# Catat referer ke login url
session.headers.update({"Referer": resp.url})

resp_login = session.post(login_url, data=payload, allow_redirects=True)
print(f"    -> Status: {resp_login.status_code}")
print(f"    -> URL setelah login: {resp_login.url}")

# Step 4: Analisis URL setelah login
# Apakah ada halaman otorisasi OAuth (Izinkan / Approve)?
if "oauth/authorize" in resp_login.url:
    print("\n[4] Terdeteksi halaman otorisasi OAuth (Consent Page).")
    soup_oauth = BeautifulSoup(resp_login.text, "html.parser")
    # Cari form approval
    approve_form = soup_oauth.find("form")
    if approve_form:
        action = approve_form.get("action", resp_login.url)
        if not action.startswith("http"):
            from urllib.parse import urljoin
            action = urljoin(resp_login.url, action)
        
        # Ambil semua input hidden dari form
        form_data = {}
        for inp in approve_form.find_all("input"):
            name = inp.get("name")
            val = inp.get("value", "")
            if name:
                form_data[name] = val
        
        print(f"    Form action: {action}")
        print(f"    Form fields: {list(form_data.keys())}")
        print("    Mengirim persetujuan 'Izinkan'...")
        session.headers.update({"Referer": resp_login.url})
        resp_after_auth = session.post(action, data=form_data, allow_redirects=True)
        print(f"    -> URL setelah otorisasi: {resp_after_auth.url}")
        resp_login = resp_after_auth
    else:
        print("[!] Form otorisasi tidak ditemukan, silakan periksa konten.")

# Step 5: Cek apakah sudah di Teraversa Homemhs
print(f"\n[5] Mencoba membuka Home Teraversa Mahasiswa...")
resp_home = session.get("https://teraversa.unsoed.ac.id/mobile/homemhs", allow_redirects=True)
print(f"    -> Status: {resp_home.status_code}")
print(f"    -> URL akhir: {resp_home.url}")

if "mobile/homemhs" in resp_home.url:
    print("\n[SUCCESS] Berhasil masuk ke Home Teraversa Mahasiswa!")
    soup_home = BeautifulSoup(resp_home.text, "html.parser")
    title = soup_home.find("title")
    print(f"    Title halaman: {title.text if title else 'No title'}")
    
    # Coba cari nama mahasiswa di halaman
    user_info = soup_home.get_text()
    for line in user_info.splitlines():
        line = line.strip()
        if "IQSAN" in line.upper() or "MAHASISWA" in line.upper():
            print(f"    Info User ditemukan: {line}")
            break

    # Cek akses ke halaman OTP
    print(f"\n[6] Mencoba akses halaman OTP: https://teraversa.unsoed.ac.id/mobile/otp")
    resp_otp = session.get("https://teraversa.unsoed.ac.id/mobile/otp", allow_redirects=True)
    print(f"    -> Status OTP: {resp_otp.status_code}")
    print(f"    -> URL OTP: {resp_otp.url}")
    
    with open("otp_page.html", "w", encoding="utf-8") as f:
        f.write(resp_otp.text)
    print("    [+] HTML halaman OTP berhasil disimpan ke otp_page.html untuk dianalisis!")

else:
    print(f"\n[FAILED] Belum berhasil mencapai https://teraversa.unsoed.ac.id/mobile/homemhs")
    with open("login_failed.html", "w", encoding="utf-8") as f:
        f.write(resp_home.text)
    print("    [!] HTML disimpan ke login_failed.html untuk debugging.")
