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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
})

# 1. Login
resp = session.get("https://teraversa.unsoed.ac.id/auth/unsoed/redirect")
soup = BeautifulSoup(resp.text, "html.parser")
csrf = soup.find("input", {"name": "_token"})["value"]

session.headers.update({"Referer": resp.url})
resp_login = session.post("https://account.unsoed.ac.id/login", data={
    "_token": csrf,
    "login": EMAIL,
    "password": PASSWORD
})

# If oauth authorize
if "oauth/authorize" in resp_login.url:
    soup_oauth = BeautifulSoup(resp_login.text, "html.parser")
    form = soup_oauth.find("form")
    form_data = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
    action = form.get("action", resp_login.url)
    resp_login = session.post(action, data=form_data)

print(f"Logged in, current URL: {resp_login.url}")

# 2. Test enterotp for one jadwal
url_enterotp = "https://teraversa.unsoed.ac.id/mobile/enterotp?idjadwal=228269"
print(f"Fetching {url_enterotp}...")
resp_enterotp = session.get(url_enterotp, headers={"X-Requested-With": "XMLHttpRequest"})
print(f"Status: {resp_enterotp.status_code}")

with open("enterotp_modal.html", "w", encoding="utf-8") as f:
    f.write(resp_enterotp.text)
print("Saved modal response to enterotp_modal.html!")
print("\n--- Content Snippet ---")
print(resp_enterotp.text[:1500])
