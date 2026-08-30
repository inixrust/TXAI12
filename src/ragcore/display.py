"""Lapisan display: mengubah chunks menjadi baris yang enak dibaca.

Dikumpulkan di satu modul karena tiga tempat mencetak daftar chunks dengan
bentuk yang sama (search.py, answer.py, dan ui). Sebelumnya ketiganya
menyalin chunks kode yang nyaris identik dengan lebar kolom yang berbeda —
persis jenis duplikasi yang membuat perbaikan kecil harus dikerjakan tiga kali.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

LINE_WIDTH = 74
SNIPPET_WIDTH = 88


def location(metadata: Mapping[str, Any]) -> str:
    """Keterangan letak chunks untuk citation, dengan nomor halaman manusia.

    PyPDFLoader menomori halaman mulai 0. Nomor mentah itu dipakai apa adanya
    oleh `testset.json` dan modul evaluasi, dan memang harus begitu — evaluasi
    membandingkan metadata, bukan teks display.

    Tetapi tidak ada dokumen yang punya "halaman 0". Menampilkannya ke users
    membuat citation tidak bisa diverifikasi: orang membuka PDF-nya, mencari
    halaman 0, dan tidak menemukan apa pun. Sitasi yang tidak bisa dicek sama
    saja dengan tidak ada citation. Karena itu penyesuaian dilakukan DI SINI, di
    lapisan display, tanpa mengubah metadata yang tersimpan di indeks.

    Urutan yang dipakai:
      1. `page_label` — label cetak asli dari PDF ("1", "ii", "A-3"). Paling
         benar: inilah yang tertulis di halaman itu sendiri.
      2. `page` + 1 — bila PDF tidak membawa label.
      3. nama bagian/bab — untuk sumber tanpa halaman, misalnya Markdown.
    """
    label = metadata.get("page_label")
    if label not in (None, ""):
        return f"hal. {label}"

    page = metadata.get("page")
    if isinstance(page, int):
        return f"hal. {page + 1}"
    if page is not None:
        return f"hal. {page}"

    section = metadata.get("bagian") or metadata.get("bab")
    return f"bagian: {section}" if section else "sumber"


def snippet(document: Any, width: int = SNIPPET_WIDTH) -> str:
    """Awal isi chunks dalam satu baris — spasi berlebih dirapikan."""
    return " ".join(document.page_content.split())[:width]


def source(document: Any) -> str:
    """Nama berkas asal chunks, atau '?' bila metadata tidak membawanya."""
    return document.metadata.get("source", "?")


def chunk_rows(number: int, document: Any, snippet_width: int = SNIPPET_WIDTH) -> str:
    """Satu baris ringkas: nomor, berkas, letak, cuplikan isi."""
    return (
        f"[{number}] {source(document)[:34]:36s} "
        f"{location(document.metadata):14s} {snippet(document, snippet_width)}..."
    )


def print_chunks(
    chunks: Iterable[Any],
    title: str | None = None,
    snippet_width: int = SNIPPET_WIDTH,
) -> None:
    """Cetak daftar chunks yang diambil.

    Kebiasaan dari modul F3: LIHAT POTONGAN SEBELUM MELIHAT JAWABAN. Ini yang
    memisahkan orang yang bisa memperbaiki sistem RAG dari orang yang hanya
    bisa mengganti-ganti prompt. Jangan dihapus.
    """
    chunks = list(chunks)
    if title:
        print(f"\n{title} — {len(chunks)} potongan")
    print("-" * LINE_WIDTH)
    for number, document in enumerate(chunks, start=1):
        print(chunk_rows(number, document, snippet_width))
    print("-" * LINE_WIDTH)
