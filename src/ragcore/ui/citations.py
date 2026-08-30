"""Membuka dokumen ASLI di balik sebuah citation.

Ini kelanjutan langsung dari alasan yang sudah ditulis panjang di
`display.lokasi()`:

    "Sitasi yang tidak bisa dicek sama saja dengan tidak ada citation."

Menampilkan "SOP-01-Kepegawaian.pdf — hal. 3" sudah lebih baik daripada tidak
ada apa-apa, tetapi users masih harus percaya. Untuk benar-benar memeriksa,
ia perlu melihat halaman 3 yang SUNGGUHAN — bukan chunks yang kebetulan
tersimpan di indeks. Kalau potongannya sendiri keliru (salah halaman, terpotong
di tempat yang salah), cuplikan dari indeks akan ikut keliru dan kekeliruannya
tidak akan pernah ketahuan.

Karena itu modul ini membaca ulang dokumen aslinya dari `config.DOCUMENT`, bukan
dari indeks. Yang ditampilkan adalah halaman asli, dengan bagian yang dibaca
model disorot di dalamnya — jadi terlihat sekaligus apa yang dipakai model dan
apa yang ada di sekitarnya.

BACA SAJA. Modul ini sengaja hanya mengembalikan TEKS, tidak pernah byte
berkasnya. Memeriksa citation dan mengunduh dokumen adalah dua kebutuhan berbeda,
dan hanya yang pertama yang dijanjikan sistem ini: satu halaman cukup untuk
memastikan jawaban benar, sedangkan berkas utuh berarti menyebarkan salinan
dokumen internal yang tak bisa ditarik kembali. Batas itu ditegakkan dengan
tidak pernah menyediakan isinya — bukan dengan menyembunyikan tombol.

Tidak ada paket baru: pypdf memang sudah dipakai lapisan indexing.
"""
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from .. import config

# Awalan "[berkas > bab > bagian]" yang ditempelkan lapisan indexing ke ISI
# chunks. Ia sengaja ada di sana agar ikut ter-embed, tapi ia BUKAN bagian
# dari dokumen asli — jadi harus dibuang sebelum dicocokkan ke halaman.
PREFIX_PATTERN = re.compile(r"^\[[^\]\n]*\]\n\n")

# <mark> bawaan peramban memaksa hitam-di-atas-kuning, yang bertabrakan dengan
# tema gelap. Sorotan tembus pandang dengan warna huruf DIWARISI terbaca pada
# tema terang maupun gelap.
HIGHLIGHT_STYLE = (
    "background:rgba(255,209,0,0.30); color:inherit; "
    "border-radius:0.15rem; padding:0.05rem 0.1rem;"
)
BOX_STYLE = (
    "white-space:pre-wrap; font-size:0.86rem; line-height:1.55; "
    "max-height:22rem; overflow-y:auto; padding:0.7rem; "
    "border:1px solid rgba(128,128,128,0.3); border-radius:0.4rem;"
)


def original_content(document: Any) -> str:
    """Isi chunks tanpa awalan konteks yang ditempelkan saat indexing."""
    return PREFIX_PATTERN.sub("", document.page_content, count=1)


def _tidy(text: str | None) -> str:
    """Rapikan spasi tanpa menghapus struktur baris.

    Spasi ganda hasil ekstraksi PDF diratakan, tapi pergantian baris
    dipertahankan — teks berpasal tak terbaca kalau dijadikan satu paragraf.
    """
    text = re.sub(r"[ \t]+", " ", text or "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------- berkas asli
@lru_cache(maxsize=64)
def _search_file(file_name: str) -> Path | None:
    """Cari berkas asli di dalam folder dokumen. None bila tak ada.

    Dicari berdasarkan nama, bukan jalur tersimpan, karena indeks bisa saja
    dibangun di mesin lain dengan jalur berbeda.
    """
    if not file_name:
        return None
    for file_path in Path(config.DOCUMENT).rglob("*"):
        if file_path.is_file() and file_path.name == file_name:
            return file_path
    return None


@lru_cache(maxsize=256)
def _pdf_page(file_path: Path, number: int, time_cap: float) -> str | None:
    """Teks satu halaman PDF.

    cap_waktu ikut menjadi kunci cache supaya berkas yang diperbarui tidak
    terus terbaca dari cache lama.
    """
    from pypdf import PdfReader

    page = PdfReader(str(file_path)).pages
    if not 0 <= number < len(page):
        return None
    return _tidy(page[number].extract_text() or "")


@lru_cache(maxsize=64)
def _text_content(file_path: Path, time_cap: float) -> str:
    return _tidy(Path(file_path).read_text(encoding="utf-8"))


def _markdown_section(text: str, metadata: Mapping[str, Any]) -> str:
    """Ambil satu bagian Markdown berdasarkan judulnya.

    Notulen dipotong per heading, jadi metadatanya menyimpan nama bab/bagian —
    bukan nomor halaman. Judul itu dicari kembali di berkas asli, lalu dipotong
    sampai judul setingkat berikutnya.
    """
    title = metadata.get("bagian") or metadata.get("bab")
    if not title:
        return text

    for level in ("## ", "# "):
        start = text.find(f"{level}{title}")
        if start == -1:
            continue
        lanjut = text.find(f"\n{level}", start + 1)
        return text[start : lanjut if lanjut != -1 else len(text)].strip()
    return text


def original_page(metadata: Mapping[str, Any]) -> tuple[str | None, str]:
    """Kembalikan (teks, keterangan) halaman/bagian asli dari sebuah citation.

    teks None berarti berkasnya tidak bisa dibaca — pemanggil harus
    mengatakannya apa adanya, bukan menampilkan halaman kosong seolah-olah
    dokumennya memang kosong.
    """
    file_path = _search_file(metadata.get("source", ""))
    if file_path is None:
        return None, f"Berkas asli tidak ditemukan di {config.DOCUMENT.name}/"

    cap = file_path.stat().st_mtime
    try:
        if file_path.suffix.lower() == ".pdf":
            number = metadata.get("page")
            if not isinstance(number, int):
                return None, "Sitasi ini tidak membawa nomor halaman."
            text = _pdf_page(file_path, number, cap)
            if text is None:
                return None, f"Halaman {number + 1} tidak ada di berkas ini."
            return text, f"Halaman asli dari {file_path.name}"
        return (
            _markdown_section(_text_content(file_path, cap), metadata),
            f"Bagian asli dari {file_path.name}",
        )
    except Exception as e:
        return None, f"Gagal membaca berkas asli: {type(e).__name__}"


# ---------------------------------------------------------------- penyorotan
def split(page_text: str, quote: str) -> tuple[str, str, str]:
    """Belah halaman menjadi (sebelum, kutipan, sesudah).

    Bila kutipan tidak ketemu, kembalikan (halaman, "", "") — halaman tetap
    ditampilkan, hanya tanpa sorotan. Ini bisa terjadi bila indeks dibangun
    dari versi dokumen yang berbeda, dan justru pantas terlihat.
    """
    if not page_text or not quote:
        return page_text or "", "", ""

    quote = _tidy(quote)
    posisi = page_text.find(quote)
    if posisi != -1:
        return (
            page_text[:posisi],
            quote,
            page_text[posisi + len(quote) :],
        )

    # Cadangan: cocokkan tanpa memedulikan pergantian baris. Pemotong kadang
    # memangkas spasi di tepi chunks sehingga pencocokan mentah meleset.
    page_flat = re.sub(r"\s+", " ", page_text)
    quote_flat = re.sub(r"\s+", " ", quote)
    posisi = page_flat.find(quote_flat)
    if posisi == -1:
        return page_text, "", ""

    def _original(flat_index: int) -> int:
        """Petakan posisi pada teks datar kembali ke teks asli."""
        skip = i = 0
        while i < len(page_text) and skip < flat_index:
            if not (
                page_text[i].isspace()
                and i + 1 < len(page_text)
                and page_text[i + 1].isspace()
            ):
                skip += 1
            i += 1
        return i

    start = _original(posisi)
    akhir = _original(posisi + len(quote_flat))
    return page_text[:start], page_text[start:akhir], page_text[akhir:]


def highlight_html(page_text: str, quote: str) -> str:
    """Halaman asli sebagai HTML, dengan bagian yang dibaca model disorot.

    Seluruh teks dokumen dilewatkan html.escape() lebih dulu. Isi dokumen
    adalah data, bukan markup — dan berkas yang memuat "<script>" tidak boleh
    berubah menjadi skrip hanya karena kita menampilkannya.
    """
    sebelum, matches, sesudah = split(page_text, quote)
    section = html.escape(sebelum)
    if matches:
        section += f"<mark style='{HIGHLIGHT_STYLE}'>{html.escape(matches)}</mark>"
    section += html.escape(sesudah)
    return f"<div style='{BOX_STYLE}'>{section}</div>"


# --------------------------------------------------------------- pemeriksaan
def check_corpus(chunks) -> tuple[int, int]:
    """Pastikan tiap chunks benar-benar bisa ditemukan kembali di aslinya.

    Uji murah yang sangat berharga: bila sebuah chunks tidak ditemukan di
    dokumen asalnya, berarti yang ditampilkan ke users sebagai 'sumber'
    tidak bisa dipertanggungjawabkan.
    """
    chunks = list(chunks)
    ketemu = 0
    for d in chunks:
        text, _ = original_page(d.metadata)
        if text is None:
            continue
        if split(text, original_content(d))[1]:
            ketemu += 1
    return ketemu, len(chunks)


@lru_cache(maxsize=32)
def _render_scan(path_str: str, page: int, dpi: int) -> bytes:
    """Render satu halaman PDF pindaian menjadi PNG. Di-cache: halaman yang
    sama berulang di banyak jawaban tidak dirender ulang."""
    import base64

    from ..extraction.vlm import page_to_image

    return base64.b64decode(page_to_image(path_str, page, dpi=dpi))


def scanned_page(metadata: Mapping[str, Any]) -> bytes | None:
    """Gambar PNG halaman PINDAIAN yang PERSIS dibaca model, atau None.

    Untuk dokumen hasil pindaian tidak ada "teks asli" untuk diperiksa - yang
    dibaca model adalah GAMBAR. Verifikasi yang jujur karena itu menampilkan
    gambar itu sendiri, bukan teks bersih yang model tak pernah lihat.
    Pengguna membandingkan bacaan model dengan halaman aslinya, dan menilai
    sendiri apakah angka yang dikutip memang ada di sana.

    DPI display sengaja lebih rendah dari DPI ekstraksi (config.DPI_RENDER):
    layar tidak butuh resolusi token visual, dan gambar yang lebih kecil
    membuat antarmuka tetap ringan.
    """
    scan = metadata.get("berkas_pindaian")
    page = metadata.get("page")
    if not scan or page is None:
        return None
    path = config.SCAN_DOCUMENT / scan
    if not path.exists():
        return None
    try:
        return _render_scan(str(path), int(page), 120)
    except Exception:      # noqa: BLE001 - render gagal bukan alasan UI mati
        return None
