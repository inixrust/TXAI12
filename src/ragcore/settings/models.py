"""Model chat, embedding, dan reranker — plus alamat Ollama dan mode tiruan.

Model vision punya modulnya sendiri (`vision`): tuning DPI-nya panjang dan
berdiri sendiri, dan mencampurnya di sini membuat keduanya sulit dibaca.
"""
from __future__ import annotations

import os

from ragcore.settings._env import flag

# ---------------------------------------------------------------- model
# Sesuaikan dengan RAM mesin Anda. Lihat reference/0002-setup-ollama.html
#   RAM  8 GB  -> "qwen3:4b"
#   RAM 16 GB  -> "qwen3:8b"
#   RAM 64 GB  -> "gpt-oss:20b"
MODEL_CHAT: str = os.getenv("MODEL_CHAT", "qwen3:8b")

# Jendela konteks untuk model chat. WAJIB DISETEL — bawaan Ollama 4096, dan
# agent hibrida menembusnya jauh sebelum peserta menyadarinya.
#
# Hitungannya: prompt sistem berisi skema basis data ~1.300 token, skema tool
# MCP ~400, chunks dokumen hasil retrieval 800-2.000, hasil query SQL bisa
# ratusan lagi, dan qwen3 masih menambah token PENALARAN di atas semua itu.
# Empat ribu habis di giliran kedua.
#
# YANG MEMBUATNYA BERBAHAYA: Ollama tidak menolak, tidak memperingatkan, dan
# tidak mencatat apa pun. Ia MEMOTONG DARI DEPAN — yang terbuang lebih dulu
# justru prompt sistemnya: aturan `ncs.`, larangan mengarang filters,
# perintah menjalankan SQL. Agent lalu berperilaku seolah tak pernah diberi
# instruksi apa pun.
#
# Terbukti di lab ini: setelah prompt sistem tumbuh ~15 baris, satu kasus
# evaluasi mulai mengembalikan JAWABAN KOSONG tanpa memanggil satu tool pun,
# selama 81 detik, tanpa errors. Yang terlihat seperti model bodoh sebenarnya
# model yang instruksinya sudah dibuang.
#
# KENAPA 8192 DAN BUKAN LEBIH BESAR. Diukur pada kasus evaluasi yang sama,
# qwen3:4b, kartu 6 GB:
#
#     num_ctx   hasil                            waktu
#     4096      jawaban kosong, nol tool         81 d
#     8192      benar, menyebut nama yang tepat  194 d
#     16384     benar tetapi hanya COUNT(*)      369 d
#
# Lebih besar bukan lebih baik. Melewati 8192, cache KV mulai menggeser bobot
# model keluar dari VRAM, dan waktu jawab hampir dua kali lipat tanpa satu pun
# jawaban menjadi lebih benar. Naikkan hanya bila konteksnya memang terbukti
# terpotong — bukan untuk berjaga-jaga.
NUM_CTX_CHAT: int = int(os.getenv("NUM_CTX_CHAT", "8192"))

# JANGAN diubah tanpa membangun ulang indeks. Lihat modul F3.
# bge-m3 dipilih karena mendukung bahasa Indonesia; nomic-embed-text tidak.
MODEL_EMBEDDING: str = os.getenv("MODEL_EMBEDDING", "bge-m3")

# Alamat layanan Ollama. Kosong = bawaan langchain (http://localhost:11434).
# Perlu diisi hanya saat aplikasi berjalan di dalam Docker, karena "localhost"
# di dalam container menunjuk container itu sendiri, bukan Ollama di host.
# Lihat DEPLOY.md. Contoh isi: http://host.docker.internal:11434
OLLAMA_URL: str = os.getenv("OLLAMA_BASE_URL", "")
DEFAULT_URL_OLLAMA: str = "http://localhost:11434"

# Reranker berjalan lewat sentence-transformers, bukan Ollama.
# Berat untuk RAM 8 GB — matikan lewat variabel USE_RERANKER=0.
MODEL_RERANKER: str = "BAAI/bge-reranker-v2-m3"
USE_RERANKER: bool = flag("USE_RERANKER", "1")

# ------------------------------------------------------------- mode tiruan
# Untuk berjaga-jaga bila Ollama bermasalah di tengah kelas.
# Aktifkan lewat variabel MODE_TIRUAN=1 (cara per-terminal ada di PANDUAN-PESERTA.md).
# Embedding diganti fungsi hash deterministik — mutunya buruk, tapi seluruh
# alur tetap berjalan sehingga peserta bisa mengikuti pelajarannya.
FAKE_MODE: bool = flag("MODE_TIRUAN")


def ollama_url() -> str:
    """Alamat Ollama yang benar-benar dipakai — untuk ditampilkan ke peserta."""
    return OLLAMA_URL or DEFAULT_URL_OLLAMA
