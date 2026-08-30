"""Model vision (VLM) dan tuning DPI untuk membaca halaman pindaian.

Angka-angka di sini diukur, bukan dikira. Tabel pengukuran dipertahankan utuh:
ia bukan basa-basi, melainkan alasan tiap nilai — dan yang mencegah orang
menyalin DPI dari model lain lalu heran kenapa ekstraksinya rusak.
"""
from __future__ import annotations

import os

from ragcore.settings._env import flag

# --------------------------------------------------------------- vision
# 3,3 GB. Dipilih agar muat di VRAM 6 GB bersama token visualnya.
MODEL_VISION: str = os.getenv("MODEL_VISION", "qwen3-vl:4b")

# DPI saat halaman PDF dirender menjadi gambar untuk VLM.
#
# Ini BUKAN DPI pemindaian. Berkas di scanned_documents/ dipindai pada 200 DPI;
# angka di bawah ini menentukan seberapa besar gambar yang dikirim ke model.
#
# ANGKA INI HARUS DIUKUR PER MODEL. Itu pelajaran utamanya, bukan angkanya.
#
# Diukur pada RTX 4050 Laptop 6 GB, halaman A4 bertabel padat (SOP-01 hal. 3),
# setiap baris didahului `ollama stop` supaya modelnya selalu segar:
#
#     model           DPI   piksel        num_ctx   hasil
#     qwen3-vl:4b     110   910 x 1287    8192      2.450 karakter, benar
#     qwen3-vl:4b     150   1241 x 1754   8192      2.472 karakter, benar
#     qwen3-vl:4b     200   1654 x 2339   8192      2.476 karakter, benar
#     qwen2.5vl:3b    110   910 x 1287    4096      2.408 karakter, benar
#     qwen2.5vl:3b    150   1241 x 1754   4096      31 karakter, RUSAK
#     qwen2.5vl:3b    150   1241 x 1754   8192      31 karakter, RUSAK
#     qwen2.5vl:3b    200   1654 x 2339   4096      GALAT: 4.252 token > 4.096
#
# Empat hal yang layak diperhatikan:
#
# 1. BATASNYA MILIK MODEL, BUKAN MILIK KARTU GRAFIS. Pada kartu yang sama,
#    qwen3-vl:4b sanggup 200 DPI sedangkan qwen2.5vl:3b sudah rusak di 150.
#    Menyalin angka DPI dari model lain adalah cara paling mudah membuat
#    ekstraksi gagal tanpa tahu sebabnya.
#
# 2. MENAIKKAN num_ctx TIDAK MENOLONG. Pada qwen2.5vl:3b @ 150 DPI hasilnya
#    rusak baik di 4096 maupun 8192, padahal promptnya muat di keduanya.
#    Kebalikan dari dugaan yang wajar ("konteksnya kurang, besarkan").
#
# 3. Hanya satu baris yang memberi GALAT. Baris RUSAK lainnya dikembalikan
#    dengan status SUKSES — model mengeluarkan satu karakter berulang
#    ('@@@@@@@...'). Tanpa degenerate_output() di vlm.py, halaman semacam
#    itu masuk indeks sebagai chunks yang sah.
#
# 4. Kerusakannya MENULAR ke halaman berikutnya. Lihat KEEP_ALIVE_VLM.
#
# 150 dipakai sebagai bawaan karena itulah yang ditetapkan silabus, dan
# terbukti benar untuk qwen3-vl:4b. Turunkan ke 110 bila memakai model
# vision yang lebih kecil.
DPI_RENDER: int = int(os.getenv("DPI_RENDER", "150"))

# DPI cadangan bila hasil pada DPI_RENDER tetap rusak setelah model dilepas.
# Turun, bukan naik — penyebabnya jumlah token visual, dan gambar yang lebih
# kecil menghasilkan lebih sedikit token.
DPI_FALLBACK: int = int(os.getenv("DPI_FALLBACK", "90"))

# Jendela konteks untuk VLM. Bawaan Ollama 4096 cukup untuk 110 DPI, tetapi
# 200 DPI sudah menembusnya (4.252 token). 8192 memberi ruang tanpa biaya
# berarti pada kartu 6 GB.
NUM_CTX_VLM: int = int(os.getenv("NUM_CTX_VLM", "8192"))

# Lepas model dari memori setiap selesai satu halaman.
#
# INI BUKAN PENGHEMATAN MEMORI, MELAINKAN KEBENARAN HASIL. Terbukti di lab:
# begitu satu halaman menghasilkan keluaran rusak, SELURUH halaman berikutnya
# ikut rusak selama model masih termuat — termasuk halaman yang sebelumnya
# terbaca sempurna. Diuji: halaman yang mengembalikan 31 karakter langsung
# mengembalikan 2.408 karakter setelah `ollama stop`, pada DPI yang sama.
#
# Kerusakannya menular, dan tidak ada satu pun errors yang menandainya.
# Harganya beberapa detik pemuatan ulang per halaman. Itu murah.
KEEP_ALIVE_VLM: str = os.getenv("KEEP_ALIVE_VLM", "0")

# Matikan mode "thinking" pada model vision.
#
# BUKAN PENGHEMATAN WAKTU — TANPA INI MODELNYA TIDAK MENGELUARKAN APA PUN.
# qwen3-vl:4b punya kemampuan thinking dan menyalakannya secara bawaan.
# Diukur pada halaman yang sama, RTX 4050 6 GB:
#
#     reasoning bawaan (nyala)  ->      0 karakter dalam 443 detik
#     reasoning=False           ->  2.450 karakter dalam 131 detik
#
# Seluruh anggaran keluaran habis dipakai berpikir, dan `content` yang
# kembali kosong. Tidak ada errors: dari luar ia terlihat seperti halaman
# yang gagal dibaca, dan tanpa pengukuran ini orang akan menyalahkan
# resolusi, VRAM, atau mutu pindaiannya.
#
# Untuk menyalin teks dari gambar, penalaran memang tidak diperlukan.
REASONING_VLM: bool = flag("REASONING_VLM", "0")

# Di bawah jumlah karakter ini, satu halaman dianggap tanpa lapisan teks.
# 50 sengaja longgar: halaman pindaian sering menyisakan nomor halaman atau
# chunks header yang ikut terbaca, dan itu bukan berarti halamannya terbaca.
EMPTY_PAGE_THRESHOLD: int = 50

# Penanda yang WAJIB dipakai VLM saat ia tidak bisa membaca sesuatu.
# Dipakai di prompt ekstraksi DAN di pemeriksaan mutu — satu tempat, karena
# keduanya harus memakai teks yang persis sama.
UNREADABLE: str = "[TIDAK TERBACA]"
EMPTY_PAGE: str = "[HALAMAN KOSONG]"
