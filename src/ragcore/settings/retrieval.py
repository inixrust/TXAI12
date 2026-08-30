"""Tuning chunking dan pencarian.

Nilai di sini menentukan MUTU jawaban, bukan sekadar perilaku. Tiap angka
punya alasan terukur pada korpus lab; menyalinnya ke korpus lain tanpa
mengukur ulang adalah cara paling umum membuat recall turun tanpa sebab yang
terlihat.
"""
from __future__ import annotations

import os

# ------------------------------------------------------------- pemotongan
CHUNK_SIZE: int = 900
OVERLAP: int = 130

# Urutan pemisah menentukan mutu chunking. Penanda pasal diletakkan paling
# atas agar pemotongan mengikuti struktur dokumen, bukan jumlah karakter.
REGULATION_SEPARATOR: list[str] = ["\nPasal ", "\nBAB ", "\n\n", "\n", ". ", " ", ""]
PROSE_SEPARATOR: list[str] = ["\n\n", "\n", ". ", " ", ""]

# Jenis dokumen (= nama subfolder di documents/) yang dipotong di batas pasal.
ARTICLED_KINDS: frozenset[str] = frozenset({"sop", "edaran"})

# ------------------------------------------------------------- pencarian
# Jumlah kandidat yang diambil TIAP pencari sebelum digabung dengan RRF.
#
# Nilai ini HARUS sebanding dengan besar korpus. Korpus lab hanya 29 chunks;
# mengambil 20 kandidat berarti hampir seluruh korpus ikut masuk, dan RRF
# kehilangan daya pilahnya — dokumen yang peringkat tengah di kedua daftar
# justru mengalahkan dokumen yang peringkat satu di salah satu daftar.
#
# Terbukti pada set uji lab: kandidat <= 10 memberi recall 100%,
# kandidat 15-20 turun menjadi 95%. Untuk korpus puluhan ribu chunks,
# 50 sampai 100 baru masuk akal.
#
# Aturan praktis: sekitar sepertiga korpus untuk korpus kecil,
# 50-100 untuk korpus besar.
N_CANDIDATES: int = 10
N_FINAL: int = 4         # dikirim ke model setelah disusun ulang

# Self-query: turunkan filters metadata dari pertanyaan (L6).
#
# MATI secara bawaan, dan itu keputusan, bukan kelalaian. Self-query menambah
# satu panggilan LLM di depan SETIAP pencarian - diukur 8 sampai 16 detik pada
# qwen3:4b. Untuk pertanyaan yang memang tanpa batasan ("berapa lama masa
# percobaan?") biayanya penuh dan manfaatnya nol.
#
# Nyalakan ketika korpus sudah cukup besar sehingga jenis dokumen dan masa
# berlaku benar-benar mempersempit, atau saat memperagakan L6 di kelas.
SELF_QUERY: bool = os.getenv("SELF_QUERY", "").lower() in ("1", "true", "ya")
