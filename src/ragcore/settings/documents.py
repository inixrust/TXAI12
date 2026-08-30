"""Kosakata dokumen dan ambang: status, kalimat baku, batas unggah.

Nilai-nilai yang dicocokkan sebagai TEKS PERSIS lintas modul. Menyatukannya
di sini bukan sekadar rapi: kalau salah satu didefinisikan dua kali dengan
ejaan berbeda, metrik yang membandingkannya diam-diam selalu bernilai nol.
"""
from __future__ import annotations

import os

# ------------------------------------------------------------- kalimat baku
# Dipakai di prompt DAN di pengukuran. Karena dicocokkan sebagai teks persis,
# ia harus didefinisikan di SATU tempat saja — kalau tidak, metrik penolakan
# akan selalu melaporkan nol tanpa ada yang menyadari.
NOT_FOUND: str = "Informasi ini tidak ditemukan dalam dokumen yang tersedia."

# ------------------------------------------------------------- kosakata status
# Status dokumen dipakai lintas modul (indexing, retrieval, evaluasi).
# Disatukan di sini agar mengubahnya tidak menuntut berburu string yang sama.
ACTIVE_STATUS: str = "berlaku"
REVOKED_STATUS: str = "dicabut"

# Penanda pada NAMA BERKAS yang menyatakan dokumen sudah dicabut. Di sistem
# sungguhan status ini datang dari basis data dokumen, bukan dari nama berkas.
REVOKED_TAGGER: str = "DICABUT"

# Ambang cakupan citation. Di bawah nilai ini, jawaban ditandai untuk diperiksa
# manual (dipakai di generation dan ui — satu sumber, bukan dua angka).
COVERAGE_THRESHOLD: float = 0.7

# ------------------------------------------------- batas jalur unggah (LLM10)
#
# UKURAN BUKAN BIAYA SEBENARNYA; HALAMAN YANG MAHAL.
#
# Sebuah PDF 40 MB bisa berisi tiga halaman gambar beresolusi tinggi, dan PDF
# 4 MB bisa berisi lima ratus halaman pindaian. Yang menentukan biaya adalah
# jumlah halaman yang harus dibaca VLM: pada mesin lab ini sekitar dua menit
# per halaman. Lima ratus halaman berarti enam belas jam GPU dari SATU
# unggahan - dan selama itu seluruh kelas menunggu queue yang sama.
#
# Karena itu keduanya dibatasi, dan yang halaman lebih menentukan. Batas ini
# ditegakkan di KODE, bukan hanya di setelan Streamlit: perintah CLI
# `commands.upload` memakai jalur yang sama dan harus tunduk aturan yang sama.
MAX_UPLOAD_MB: float = float(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_PAGES: int = int(os.getenv("MAX_UPLOAD_PAGES", "60"))
