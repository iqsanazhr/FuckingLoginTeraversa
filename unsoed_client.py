import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

class UnsoedClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.user_name = None

    def login(self, email: str, password: str) -> tuple[bool, str, str]:
        """
        Login ke SSO Unsoed dan Teraversa.
        Mengembalikan (is_success, user_name, error_message).
        """
        try:
            # 1. Mulai dari SSO redirect Teraversa
            redirect_url = "https://teraversa.unsoed.ac.id/auth/unsoed/redirect"
            resp = self.session.get(redirect_url, allow_redirects=True, timeout=15)
            
            # 2. Ambil token CSRF di halaman login account.unsoed.ac.id
            soup = BeautifulSoup(resp.text, "html.parser")
            csrf_input = soup.find("input", {"name": "_token"})
            
            if not csrf_input:
                resp = self.session.get("https://account.unsoed.ac.id/login", timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                csrf_input = soup.find("input", {"name": "_token"})
                
            if not csrf_input:
                return False, "", "Gagal mendapatkan form login CSRF dari server Unsoed."

            csrf_token = csrf_input.get("value")

            # 3. Kirim kredensial
            login_url = "https://account.unsoed.ac.id/login"
            self.session.headers.update({"Referer": resp.url})
            payload = {
                "_token": csrf_token,
                "login": email,
                "password": password,
            }
            resp_login = self.session.post(
                login_url,
                data=payload,
                allow_redirects=True,
                timeout=15,
            )
            # Hapus data password seketika dari memori proses
            del payload
            del password

            # Cek jika kredensial salah
            if "account.unsoed.ac.id/login" in resp_login.url:
                # Login gagal
                err_soup = BeautifulSoup(resp_login.text, "html.parser")
                err_box = err_soup.find(class_=lambda c: c and ("error" in c.lower() or "alert" in c.lower() or "invalid" in c.lower()))
                err_msg = err_box.get_text(strip=True) if err_box else "Email atau password Unsoed salah."
                return False, "", err_msg

            # 4. Handle halaman otorisasi OAuth (jika ada tombol Izinkan / Consent)
            if "oauth/authorize" in resp_login.url:
                soup_oauth = BeautifulSoup(resp_login.text, "html.parser")
                approve_form = soup_oauth.find("form")
                if approve_form:
                    action = approve_form.get("action", resp_login.url)
                    form_data = {
                        inp.get("name"): inp.get("value", "")
                        for inp in approve_form.find_all("input")
                        if inp.get("name")
                    }
                    self.session.headers.update({"Referer": resp_login.url})
                    resp_login = self.session.post(action, data=form_data, allow_redirects=True, timeout=15)

            # 5. Buka Home Teraversa untuk verifikasi dan ambil nama mahasiswa
            resp_home = self.session.get("https://teraversa.unsoed.ac.id/mobile/homemhs", timeout=15)
            if "mobile/homemhs" in resp_home.url or "homemhs" in resp_home.url:
                soup_home = BeautifulSoup(resp_home.text, "html.parser")
                user_detail = soup_home.find("div", class_="user-details")
                if user_detail and user_detail.find("b"):
                    self.user_name = user_detail.find("b").get_text(strip=True)
                else:
                    self.user_name = "Mahasiswa Unsoed"
                return True, self.user_name, ""
            else:
                return False, "", "Berhasil autentikasi SSO namun gagal diarahkan ke Teraversa Home."

        except Exception as e:
            return False, "", f"Koneksi error: {str(e)}"

    def get_courses(self) -> list[dict]:
        """
        Mengambil daftar mata kuliah aktif dari https://teraversa.unsoed.ac.id/mobile/otp
        """
        try:
            resp = self.session.get("https://teraversa.unsoed.ac.id/mobile/otp", timeout=15)
            if "mobile/otp" not in resp.url and "homemhs" not in resp.url:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="card")
            courses = []

            for card in cards:
                title_tag = card.find("h5")
                if not title_tag:
                    continue
                course_name = title_tag.get_text(strip=True)

                # Ambil jadwal
                list_group = card.find("div", class_="list-group")
                schedule_text = ""
                if list_group:
                    # Jadwal ada di teks setelah h5
                    for content in list_group.contents:
                        if isinstance(content, str):
                            text = content.strip()
                            if text and any(day in text.upper() for day in ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU", "MINGGU"]):
                                schedule_text = text
                                break

                # Ambil link button OTP
                btn_otp = card.find("a", class_=lambda c: c and "btn-otp-presensi" in c)
                idjadwal = ""
                if btn_otp and btn_otp.get("data-attr"):
                    attr_url = btn_otp["data-attr"]
                    parsed = parse_qs(urlparse(attr_url).query)
                    idjadwal = parsed.get("idjadwal", [""])[0]

                if idjadwal:
                    # Buat alias singkatan otomatis (misal: "Uji Kualitas Perangkat Lunak (A)" -> "UPL")
                    alias = self._generate_alias(course_name)
                    courses.append({
                        "idjadwal": idjadwal,
                        "name": course_name,
                        "schedule": schedule_text,
                        "alias": alias,
                    })

            return courses

        except Exception as e:
            print(f"[ERROR] get_courses: {e}")
            return []

    def submit_otp(self, idjadwal: str, token: str) -> tuple[bool, str]:
        """
        Submit token OTP presensi ke Teraversa.
        Mengembalikan (is_success, message).
        """
        try:
            # 1. Buka modal enterotp untuk mendapatkan CSRF token modal
            modal_url = f"https://teraversa.unsoed.ac.id/mobile/enterotp?idjadwal={idjadwal}"
            resp_modal = self.session.get(
                modal_url,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=15,
            )

            if resp_modal.status_code != 200:
                return False, f"Gagal memuat form presensi (HTTP {resp_modal.status_code})"

            soup_modal = BeautifulSoup(resp_modal.text, "html.parser")
            form = soup_modal.find("form")
            if not form:
                return False, "Form input token tidak ditemukan di sistem kampus."

            token_input = form.find("input", {"name": "_token"})
            if not token_input:
                return False, "CSRF token form presensi tidak ditemukan."

            csrf_token = token_input.get("value")

            # 2. Kirim POST token
            post_url = form.get("action", "https://teraversa.unsoed.ac.id/mobile/prosesotp")
            self.session.headers.update({"Referer": "https://teraversa.unsoed.ac.id/mobile/otp"})

            resp_submit = self.session.post(
                post_url,
                data={
                    "_token": csrf_token,
                    "idjadwal": idjadwal,
                    "token": str(token).strip(),
                },
                allow_redirects=True,
                timeout=15,
            )

            # 3. Analisis pesan balasan dari server
            soup_res = BeautifulSoup(resp_submit.text, "html.parser")

            # Cari alert box
            alerts = soup_res.find_all(class_=lambda c: c and ("alert" in c.lower() or "swal" in c.lower()))
            alert_msg = ""
            for a in alerts:
                text = a.get_text(strip=True)
                if text:
                    alert_msg += text + " "

            alert_msg = alert_msg.strip()

            # Periksa pesan umum
            if not alert_msg:
                # Cek di script SweetAlert
                for s in soup_res.find_all("script"):
                    if s.string and "Swal.fire" in s.string:
                        # Extract title / text
                        match = re.search(r"title\s*:\s*['\"]([^'\"]+)['\"]", s.string)
                        text_match = re.search(r"text\s*:\s*['\"]([^'\"]+)['\"]", s.string)
                        title = match.group(1) if match else ""
                        body = text_match.group(1) if text_match else ""
                        alert_msg = f"{title} - {body}".strip(" -")
                        break

            # Jika masih kosong
            if not alert_msg:
                if "Token salah" in resp_submit.text:
                    alert_msg = "Token salah / Expired, coba ulangi. Cek pada log perkuliahan Anda."
                elif "berhasil" in resp_submit.text.lower():
                    alert_msg = "Presensi berhasil dicatat!"
                else:
                    alert_msg = "Presensi telah diproses."

            # Tentukan status sukses atau gagal
            is_success = not any(err_word in alert_msg.lower() for err_word in ["salah", "expired", "gagal", "tidak aktif", "error"])

            return is_success, alert_msg

        except Exception as e:
            return False, f"Gagal submit token: {str(e)}"

    def _generate_alias(self, course_name: str) -> str:
        """
        Menghasilkan alias / singkatan yang jelas dan unik (minimal 2-4 huruf).
        Contoh:
        'Kriptografi (A)' -> 'KRIPTO'
        'Kewirausahaaan (A)' -> 'KWU'
        'Uji Kualitas Perangkat Lunak (A)' -> 'UKPL'
        'Enterprise Resources Planing (ERP) (A)' -> 'ERP'
        """
        name_lower = course_name.lower()

        # 1. Cek singkatan resmi dalam kurung seperti (ERP)
        match_bracket = re.search(r"\(([A-Z]{2,6})\)", course_name)
        if match_bracket:
            return match_bracket.group(1)

        # 2. Kamus singkatan umum perkuliahan
        common_map = {
            "kriptografi": "KRIPTO",
            "kewirausahaan": "KWU",
            "kewirausahaaan": "KWU",
            "olah raga": "OR",
            "olahraga": "OR",
            "kerja praktek": "KP",
            "keamanan informasi": "KI",
            "pemrograman mobile": "PM",
            "praktikum pemrograman mobile": "PPM",
            "manajemen proyek informatika": "MPI",
            "uji kualitas perangkat lunak": "UKPL",
            "enterprise resources planing": "ERP",
            "basis data": "BASDAT",
            "struktur data": "STRUKDAT",
            "jaringan komputer": "JARKOM",
            "kecerdasan buatan": "AI",
        }

        # Bersihkan akhiran kelas seperti '(A)', '(B)', '(1)'
        cleaned = re.sub(r"\([A-Za-z0-9\s]+\)", "", course_name).strip()
        cleaned_lower = cleaned.lower()

        # Urutkan berdasarkan panjang kunci terpanjang agar frasa seperti
        # 'praktikum pemrograman mobile' cocok sebelum 'pemrograman mobile'
        sorted_keys = sorted(common_map.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in cleaned_lower:
                return common_map[key]

        # 3. Jika lebih dari 1 kata, ambil huruf depan tiap kata
        words = [w for w in cleaned.split() if w.isalpha()]
        stopwords = {"dan", "atau", "pada", "di", "ke", "dari", "untuk", "dalam"}
        meaningful_words = [w for w in words if w.lower() not in stopwords]
        if not meaningful_words:
            meaningful_words = words

        if len(meaningful_words) == 1:
            # Jika hanya 1 kata (misal: Aljabar, Fisika, Kriptografi)
            # Ambil 3-5 huruf pertama agar minimal 2-4 huruf
            word = meaningful_words[0]
            if len(word) <= 5:
                return word.upper()
            return word[:5].upper()

        alias = "".join([w[0].upper() for w in meaningful_words])
        if len(alias) < 2 and meaningful_words:
            alias = meaningful_words[0][:3].upper()

        return alias
