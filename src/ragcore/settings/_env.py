"""Fondasi setelan: membaca .env dan menafsir flag ya/tidak.

Sengaja hanya memakai pustaka bawaan Python. Seluruh paket `settings` mewarisi
batas itu: `check.py` mengimpornya sebelum memastikan paket lain terpasang -
kalau di sini ada `import langchain`, pemeriksaan kesiapan justru gagal pada
mesin yang paling membutuhkannya.
"""
from __future__ import annotations

import os
from pathlib import Path

# Akar lab. Letak berkas ini: lab/src/ragcore/settings/_env.py
#   parents[0]=settings  [1]=ragcore  [2]=src  [3]=lab
# ROOT harus menunjuk folder lab/, karena dokumen, indeks, dan set uji ada di
# sana — bukan di dalam src/. Sesuaikan angkanya bila berkas ini dipindahkan.
ROOT: Path = Path(__file__).resolve().parents[3]


def load_env(file: str = ".env") -> None:
    """Baca .env bila ada, tanpa menimpa yang sudah disetel di shell.

    KENAPA DITULIS SENDIRI, BUKAN MEMAKAI python-dotenv.

    Bukan karena pustakanya buruk, melainkan karena README lab ini sudah
    menyuruh peserta "isi LANGFUSE_PUBLIC_KEY di .env" sejak lama - dan
    sampai perbaikan ini, TIDAK ADA SATU BARIS PUN yang membaca berkas itu.
    Peserta mengisi, menjalankan, dan jejaknya tetap mati tanpa satu pun
    pesan yang menjelaskan kenapa. Janji dokumentasi yang tidak ditepati kode
    adalah cacat, dan menambah dependensi untuk menepatinya terasa berlebihan
    untuk dua belas baris.

    Yang disetel di shell MENANG atas isi berkas. Dengan begitu perintah
    seperti `STORAGE=chroma python -m ...` tetap berlaku meski .env menyebut
    sebaliknya - kalau tidak, peserta akan mengubah perintah dan bingung
    kenapa tidak berpengaruh.
    """
    file_path = ROOT / file
    if not file_path.exists():
        return
    for row in file_path.read_text(encoding="utf-8").splitlines():
        row = row.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, _, value = row.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def flag(name: str, default: str = "0") -> bool:
    """Baca variabel lingkungan sebagai ya/tidak.

    Cara menyetelnya per-terminal (PowerShell/cmd/bash) ada di
    PANDUAN-PESERTA.md. Nilai yang dianggap "ya": 1, true, ya, y.
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "ya", "y"}
