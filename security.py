"""
Modul Keamanan & Kriptografi: Zero-Knowledge E2EE dengan 4-Digit Personal PIN
Standar Keamanan: AES-256-GCM + PBKDF2-HMAC-SHA256 (100,000 iterasi)
Developer: nctreap_
"""

import base64
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from config import APP_SECRET_KEY


def derive_key_from_pin(pin: str, salt: bytes) -> bytes:
    """
    Menurunkan kunci 256-bit (32 bytes) dari PIN 4-digit menggunakan PBKDF2-HMAC-SHA256.
    Iterasi: 100.000 kali untuk mencegah serangan brute-force secara komputasi.
    """
    if not pin or len(pin) != 4 or not pin.isdigit():
        raise ValueError("PIN harus berupa 4 digit angka!")
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations=100000)


def encrypt_with_pin(plaintext: str, pin: str) -> tuple[str, str]:
    """
    Enkripsi password menggunakan PIN 4-digit milik pengguna.
    Menggunakan salt 128-bit unik dan nonce 96-bit unik.
    Output: (encrypted_b64, salt_b64)
    """
    if not plaintext:
        return "", ""
    salt = os.urandom(16)  # 128-bit random salt
    key = derive_key_from_pin(pin, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    
    payload = nonce + ciphertext
    return (
        base64.b64encode(payload).decode("utf-8"),
        base64.b64encode(salt).decode("utf-8")
    )


def decrypt_with_pin(encrypted_b64: str, salt_b64: str, pin: str) -> str:
    """
    Dekripsi password menggunakan PIN 4-digit milik pengguna.
    Jika PIN salah, algoritma AESGCM otomatis melempar InvalidTag (verifikasi gagal).
    """
    if not encrypted_b64 or not salt_b64:
        return ""
    try:
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        key = derive_key_from_pin(pin, salt)
        aesgcm = AESGCM(key)
        raw_data = base64.b64decode(encrypted_b64.encode("utf-8"))
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except (InvalidTag, ValueError):
        raise ValueError("PIN 4-digit salah! Kunci dekripsi tidak valid.")


# --- Fallback Master Key (Kompatibilitas Sistem Sebelumnya) ---
def _get_key_bytes() -> bytes:
    if not APP_SECRET_KEY:
        return hashlib.sha256(b"default-fallback-secret-2026").digest()
    if len(APP_SECRET_KEY) == 64:
        try:
            return bytes.fromhex(APP_SECRET_KEY)
        except ValueError:
            pass
    return hashlib.sha256(APP_SECRET_KEY.encode()).digest()


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_secret(encrypted_b64: str) -> str:
    if not encrypted_b64:
        return ""
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    raw_data = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = raw_data[:12]
    ciphertext = raw_data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


if __name__ == "__main__":
    test_pwd = "AkunUnsoed123!@"
    pin_user = "1234"
    
    print("[*] Menguji Zero-Knowledge E2EE PIN...")
    enc_data, salt_data = encrypt_with_pin(test_pwd, pin_user)
    print(f"    Encrypted : {enc_data[:30]}...")
    print(f"    Salt      : {salt_data}")
    
    # Tes dekripsi sukses dengan PIN benar
    dec_pwd = decrypt_with_pin(enc_data, salt_data, "1234")
    assert dec_pwd == test_pwd
    print("[+] Dekripsi dengan PIN benar '1234': SUKSES!")
    
    # Tes dekripsi gagal dengan PIN salah
    try:
        decrypt_with_pin(enc_data, salt_data, "9999")
        print("[-] GAGAL: PIN salah harusnya ditolak!")
    except ValueError as e:
        print(f"[+] Proteksi berhasil: PIN salah '9999' ditolak ({e})")
