"""
Modul Pemindai & Deteksi QR Code (Computer Vision)
Menggunakan OpenCV QRCodeDetector dengan Multi-Stage Enhancement
Developer: nctreap_
"""

import cv2
import numpy as np


def scan_qr_from_bytes(image_bytes: bytes) -> str:
    """
    Mendeteksi dan mengekstrak teks dari QR Code di dalam buffer byte gambar.
    Menerapkan pipeline multi-stage (Color -> Grayscale -> Otsu Thresholding)
    untuk memaksimalkan deteksi foto dari layar proyektor atau kamera HP yang redup.
    """
    if not image_bytes:
        return ""

    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        detector = cv2.QRCodeDetector()

        # Tahap 1: Deteksi langsung pada gambar asli
        data, _, _ = detector.detectAndDecode(img)
        if data and data.strip():
            return data.strip()

        # Tahap 2: Deteksi pada gambar Grayscale (mengurangi noise warna)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data, _, _ = detector.detectAndDecode(gray)
        if data and data.strip():
            return data.strip()

        # Tahap 3: Deteksi dengan Adaptive Thresholding / Binarization (mengatasi pantulan cahaya proyektor)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 5
        )
        data, _, _ = detector.detectAndDecode(thresh)
        if data and data.strip():
            return data.strip()

        # Tahap 4: Histogram Equalization (meningkatkan kontras)
        eq = cv2.equalizeHist(gray)
        data, _, _ = detector.detectAndDecode(eq)
        if data and data.strip():
            return data.strip()

        return ""
    except Exception as e:
        return ""


if __name__ == "__main__":
    print("[*] Modul qr_scanner siap digunakan.")
