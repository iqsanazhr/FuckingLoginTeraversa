import os
import sys
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import json

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

# 1. Inspect https://teraversa.unsoed.ac.id/mobile/rekaphispresensi
print("[*] Fetching /mobile/rekaphispresensi...")
resp = client.session.get("https://teraversa.unsoed.ac.id/mobile/rekaphispresensi", timeout=15)
print(f"Status Code: {resp.status_code}, Final URL: {resp.url}")

soup = BeautifulSoup(resp.text, "html.parser")

# Cari table atau elemen card
tables = soup.find_all("table")
print(f"Found {len(tables)} tables")

for idx, table in enumerate(tables):
    print(f"\n--- Table {idx+1} ---")
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    print("Headers:", headers)
    
    rows = table.find_all("tr")
    for r in rows[:5]:
        cols = [td.get_text(strip=True) for td in r.find_all("td")]
        links = [a.get("href") for a in r.find_all("a")]
        if cols:
            print("Row cols:", cols, "Links:", links)

# Check all links with hispresensi
his_links = soup.find_all("a", href=lambda h: h and "hispresensi" in h)
print(f"\nFound {len(his_links)} hispresensi links:")
for a in his_links[:3]:
    print("Text:", a.get_text(strip=True), "| Href:", a.get("href"))

# 2. If there is a hispresensi link, inspect the first detail page
if his_links:
    first_url = his_links[0].get("href")
    if not first_url.startswith("http"):
        first_url = f"https://teraversa.unsoed.ac.id{first_url}"
    print(f"\n[*] Fetching detail page: {first_url}...")
    detail_resp = client.session.get(first_url, timeout=15)
    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
    
    detail_tables = detail_soup.find_all("table")
    print(f"Found {len(detail_tables)} detail tables")
    for idx, dt in enumerate(detail_tables):
        d_headers = [th.get_text(strip=True) for th in dt.find_all("th")]
        print(f"Detail Table {idx+1} Headers:", d_headers)
        for dr in dt.find_all("tr")[:5]:
            d_cols = [td.get_text(strip=True) for td in dr.find_all("td")]
            if d_cols:
                print("Detail row:", d_cols)
