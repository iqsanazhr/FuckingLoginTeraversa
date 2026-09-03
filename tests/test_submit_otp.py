import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
EMAIL = os.getenv("UNSOED_EMAIL")
PASSWORD = os.getenv("UNSOED_PASSWORD")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
})

# Login
resp = session.get("https://teraversa.unsoed.ac.id/auth/unsoed/redirect")
soup = BeautifulSoup(resp.text, "html.parser")
csrf = soup.find("input", {"name": "_token"})["value"]
session.headers.update({"Referer": resp.url})
resp_login = session.post("https://account.unsoed.ac.id/login", data={
    "_token": csrf,
    "login": EMAIL,
    "password": PASSWORD
})

# Get enterotp modal
url_enterotp = "https://teraversa.unsoed.ac.id/mobile/enterotp?idjadwal=228269"
resp_modal = session.get(url_enterotp, headers={"X-Requested-With": "XMLHttpRequest"})
soup_modal = BeautifulSoup(resp_modal.text, "html.parser")
form = soup_modal.find("form")
form_token = form.find("input", {"name": "_token"})["value"]
idjadwal = form.find("input", {"name": "idjadwal"})["value"]

print(f"Form found: action={form.get('action')}, _token={form_token[:10]}..., idjadwal={idjadwal}")

# Test submit dummy token
payload = {
    "_token": form_token,
    "token": "000000",
    "idjadwal": idjadwal
}
session.headers.update({"Referer": "https://teraversa.unsoed.ac.id/mobile/otp"})
resp_submit = session.post("https://teraversa.unsoed.ac.id/mobile/prosesotp", data=payload, allow_redirects=True)

print(f"Submit status: {resp_submit.status_code}")
print(f"Submit URL: {resp_submit.url}")

# Cari alert / flash message di response
soup_res = BeautifulSoup(resp_submit.text, "html.parser")
alerts = soup_res.find_all(class_=lambda c: c and ("alert" in c or "swal" in c or "modal" in c))
for a in alerts:
    text = a.get_text(strip=True)
    if text:
        print(f"Alert found: {text}")

# Cari script sweetalert atau pesan javascript
import re
scripts = soup_res.find_all("script")
for s in scripts:
    if s.string and ("Swal" in s.string or "alert" in s.string or "message" in s.string or "pesan" in s.string):
        print(f"Script alert/message:\n{s.string.strip()[:300]}")
