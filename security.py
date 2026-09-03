import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import APP_SECRET_KEY

# Pastikan secret key memiliki panjang 32 bytes (256-bit)
def _get_key_bytes() -> bytes:
    if not APP_SECRET_KEY:
        raise ValueError("APP_SECRET_KEY belum diset di .env!")
    
    # Jika dalam bentuk hex 64 char -> decode ke 32 bytes
    if len(APP_SECRET_KEY) == 64:
        try:
            return bytes.fromhex(APP_SECRET_KEY)
        except ValueError:
            pass
    
    # Fallback padding/hashing jika panjangnya berbeda
    import hashlib
    return hashlib.sha256(APP_SECRET_KEY.encode()).digest()

def encrypt_secret(plaintext: str) -> str:
    """
    Enkripsi string dengan standar AES-256-GCM (Authenticated Encryption).
    Menggunakan nonce 96-bit (12-byte) unik setiap enkripsi.
    Output dalam format Base64: [12-byte nonce] + [ciphertext + tag]
    """
    if not plaintext:
        return ""
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit cryptographically secure nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("utf-8")

def decrypt_secret(encrypted_b64: str) -> str:
    """
    Dekripsi data AES-256-GCM dan verifikasi tag autentikasi.
    """
    if not encrypted_b64:
        return ""
    key = _get_key_bytes()
    aesgcm = AESGCM(key)
    raw_data = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = raw_data[:12]
    ciphertext = raw_data[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")

if __name__ == "__main__":
    # Test enkripsi & dekripsi
    test_str = "PasswordSangatRahasia123!@"
    enc = encrypt_secret(test_str)
    dec = decrypt_secret(enc)
    assert test_str == dec
    print(f"[+] Enkripsi AES-256-GCM berhasil diverifikasi!")
    print(f"    Plaintext: {test_str}")
    print(f"    Ciphertext Base64: {enc}")
