"""Letak berkas: dokumen, indeks, cache, set uji.

Semua jalur berlabuh pada ROOT (folder lab), bukan pada src/. Menyatukannya
di sini berarti memindahkan lab ke struktur folder lain hanya menyentuh satu
berkas.
"""
from __future__ import annotations

from pathlib import Path

from ragcore.settings._env import ROOT

# ------------------------------------------------------------- lokasi
DOCUMENT: Path = ROOT / "documents"
INDEX: Path = ROOT / "chroma_db"
CHUNKS_FILE: Path = ROOT / "chunks.json"
TEST_SET: Path = ROOT / "testset.json"
COLLECTION_NAME: str = "korpus_ncs"

# Sidik jari indeks: mencatat DENGAN APA indeks dibangun (lihat fingerprint.py).
# Dipakai untuk menolak diam-diamnya kegagalan F3 — indeks yang dibangun
# dengan embedding berbeda memberi hasil acak tanpa errors apa pun.
META: Path = ROOT / "index_meta.json"

# ------------------------------------------------------------- lokasi TX-AI12
# Dokumen asli yang PUNYA versi pindaian. Tidak ikut diindeks: kalau ia
# masuk korpus, aturannya bisa dibaca tanpa menyentuh VLM sama sekali, dan
# rantai Hari 1 -> Hari 3 kehilangan seluruh maknanya. Dipakai hanya oleh
# make_scans.py saat membangkitkan ulang korpus pindaian.
ORIGINAL_SOURCE: Path = ROOT / "source_originals"

SCAN_DOCUMENT: Path = ROOT / "scanned_documents"
HYBRID_TEST_SET: Path = ROOT / "testset_hybrid.json"

# Singgahan hasil ekstraksi VLM, berdampingan dengan PDF-nya (berkas .vlm.txt).
# Ekstraksi ulang satu arsip bisa memakan berjam-jam; singgahan membuat
# indexing ulang menjadi hitungan detik.
CACHE_SUFFIX: str = ".vlm.txt"
