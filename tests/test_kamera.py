import os
import sys
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from unsoed_client import UnsoedClient

load_dotenv()
email = os.getenv("UNSOED_EMAIL")
password = os.getenv("UNSOED_PASSWORD")

print("[*] Logging in to Unsoed...")
client = UnsoedClient()
ok, name, err = client.login(email, password)
if not ok:
    print(f"[-] Login failed: {err}")
    sys.exit(1)

print(f"[+] Logged in as: {name}")

# Fetch https://teraversa.unsoed.ac.id/mobile/kamera
print("[*] Fetching /mobile/kamera...")
resp = client.session.get("https://teraversa.unsoed.ac.id/mobile/kamera", timeout=15)
print(f"Status Code: {resp.status_code}, Final URL: {resp.url}")

soup = BeautifulSoup(resp.text, "html.parser")

# 1. Cari form
forms = soup.find_all("form")
print(f"\nFound {len(forms)} forms:")
for f in forms:
    print("Action:", f.get("action"), "| Method:", f.get("method"), "| Inputs:", [i.get("name") for i in f.find_all("input")])

# 2. Cari script dan AJAX
scripts = soup.find_all("script")
print(f"\nFound {len(scripts)} scripts")
for idx, s in enumerate(scripts):
    content = s.string or s.get_text() or ""
    src = s.get("src", "")
    if src:
        print(f"Script {idx+1} src: {src}")
    if content:
        # Cari kata kunci: qr, scan, upload, url, post, proses, token, fetch, ajax
        matches = re.findall(r"(?:qr|scan|upload|proses|kamera|token|jadwal|ajax|fetch)[a-zA-Z0-9_/:\-\.]*", content, re.IGNORECASE)
        if matches:
            print(f"\n--- Script {idx+1} Keywords ({len(matches)} matches) ---")
            for line in content.split("\n"):
                if any(k in line.lower() for k in ["post", "fetch", "url", "qr", "proses", "action", "upload"]):
                    print("  >", line.strip()[:150])

# 3. Simpan seluruh HTML ke file scratch untuk analisis detail
with open("tests/kamera_page.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("\n[+] Full HTML saved to tests/kamera_page.html")
