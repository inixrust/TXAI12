"""Metadata chunks: status dokumen dan jalur judul.

Dua hal kecil yang menentukan mutu seluruh sistem di hilir — penyaringan
status (B3) dan konteks induk yang ikut di-embed (B2).
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from ragcore.domain import Document

from .. import config

# Urutan bagian jalur judul yang ditempelkan ke isi chunks.
PATH_SECTION = ("source", "bab", "bagian")

# ------------------------------------------------- kepemilikan dokumen (L6)
# Unit pemilik dan klasifikasi tiap dokumen. Di sistem sungguhan ini datang
# dari basis data dokumen atau dari metadata pada sistem arsip — BUKAN dari
# nama berkas. Untuk lab, peta ini cukup dan mudah dilihat peserta.
#
# Yang penting dirancang di sini bukan datanya, melainkan sebarannya: harus
# ada dokumen umum (terlihat semua orang) DAN dokumen terbatas milik unit
# berbeda. Kalau semuanya umum, peragaan RLS pada L6 menghasilkan angka yang
# sama untuk setiap users, dan seluruh pelajarannya hilang.
OWNERSHIP: dict[str, tuple[str, str]] = {
    # awalan nama berkas   : (unit pemilik,       klasifikasi)
    "SOP-01": ("Divisi SDM", "umum"),
    "SOP-02": ("Divisi Pengadaan", "umum"),
    "SOP-03": ("Divisi TI", "terbatas"),
    "SOP-05": ("Divisi TI", "terbatas"),
    "SE-12": ("Direksi", "umum"),
    "NR-04": ("Divisi TI", "terbatas"),
}

DEFAULT_UNIT = "Umum"
DEFAULT_CLASSIFICATION = "umum"


def ownership(file_name: str) -> tuple[str, str]:
    """Kembalikan (unit, klasifikasi) untuk satu dokumen."""
    for prefix, value in OWNERSHIP.items():
        if file_name.upper().startswith(prefix.upper()):
            return value
    return DEFAULT_UNIT, DEFAULT_CLASSIFICATION


def document_status(file_name: str) -> str:
    """Dokumen dengan penanda DICABUT pada namanya ditandai agar bisa disaring.

    Di sistem sungguhan status ini datang dari basis data dokumen, bukan dari
    nama berkas. Untuk lab, cara ini cukup dan mudah dilihat peserta.
    """
    return (
        config.REVOKED_STATUS
        if config.REVOKED_TAGGER in file_name.upper()
        else config.ACTIVE_STATUS
    )


# ------------------------------------------------------- metadata waktu (L6)
# Bulan Indonesia -> nomor. Dokumen lab menuliskan tanggal dalam bentuk
# "1 Februari 2026", bukan ISO.
_MONTH = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
}

# Tiga bentuk yang benar-benar muncul di korpus ini:
#   "Nomor: SE-12/NCS/DIR/2026 | Berlaku sejak: 1 Februari 2026"
#   "DICABUT sejak 1 Maret 2026 melalui SK-08/NCS/DIR/2026."
#   "**Tanggal:** 18 Maret 2026, pukul 09.00 - 11.15"      (notulen)
_PATTERN = {
    "tanggal_berlaku": re.compile(
        r"berlaku\s+sejak\s*:?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE),
    "tanggal_cabut": re.compile(
        r"dicabut\s+sejak\s*:?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE),
    "tanggal_dokumen": re.compile(
        r"tanggal\s*:?\**\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE),
}


def _iso(day: str, month: str, tahun: str) -> str | None:
    number = _MONTH.get(month.lower())
    if not number:
        return None
    try:
        return date(int(tahun), number, int(day)).isoformat()
    except ValueError:
        return None


def dates_from_text(text: str) -> dict[str, str]:
    """Tanggal berlaku / cabut / dokumen, dibaca dari ISI dokumen.

    KENAPA DARI ISI, BUKAN DARI NAMA BERKAS ATAU WAKTU BERKAS.

    Nama berkas hanya memuat tahun, dan itu tidak cukup: SOP-05 berlaku
    1 Maret 2026 sementara SOP-02 berlaku 12 Januari 2026 - keduanya "2026".
    Waktu modifikasi berkas lebih buruk lagi: ia berubah saat berkas disalin,
    dan di lab ini seluruh korpus akan bertanggal sama, yaitu hari pelatihan.

    Yang dicari adalah tanggal yang DINYATAKAN DOKUMEN TENTANG DIRINYA:

        Nomor: SE-12/NCS/DIR/2026 | Berlaku sejak: 1 Februari 2026
        DICABUT sejak 1 Maret 2026 melalui SK-08/NCS/DIR/2026.

    Itu satu-satunya tanggal yang punya arti organisasi. Perhatikan bahwa
    tanggal ini datang lewat jalur VLM untuk dokumen pindaian - satu digit
    yang salah baca menggeser masa berlaku sebuah aturan, dan tidak ada
    errors yang akan memberi tahu.
    """
    result: dict[str, str] = {}
    for name, pattern in _PATTERN.items():
        m = pattern.search(text or "")
        if not m:
            continue
        iso = _iso(*m.groups())
        if iso:
            result[name] = iso
    # "Berlaku sejak" lebih spesifik daripada "Tanggal"; jangan sampai pola
    # umum menimpanya pada dokumen yang memuat keduanya.
    if "tanggal_berlaku" in result:
        result.pop("tanggal_dokumen", None)
    return result


def add_context(
    chunks: Iterable[Document], kind: str, file_name: str
) -> list[Document]:
    """Sisipkan jalur judul ke ISI chunks, bukan hanya ke metadata.

    Metadata tidak ikut di-embed. Kalau konteks induk hanya ditaruh di sana,
    ia tidak membantu pencarian sama sekali — pelajaran B2.
    """
    chunks = list(chunks)

    # Tanggal dibaca SEKALI dari seluruh isi dokumen, lalu dipasang ke semua
    # potongannya. Barisnya hanya ada di halaman pertama, sementara filters
    # bekerja di tingkat chunks - chunks halaman 3 tetap harus tahu kapan
    # dokumennya mulai berlaku.
    time = dates_from_text("\n".join(d.page_content for d in chunks))
    today = date.today().isoformat()

    result: list[Document] = []
    for document in chunks:
        m = document.metadata
        m.update(time)
        # Kapan chunks ini masuk indeks. Bukan tanggal dokumen, dan tidak
        # boleh tertukar: yang satu menjawab "aturannya sejak kapan berlaku",
        # yang lain menjawab "kapan terakhir kali kita membacanya". Pertanyaan
        # kedua itu yang muncul saat seseorang bertanya kenapa jawabannya
        # masih memakai revisi lama.
        m["tanggal_indeks"] = today
        m.setdefault("source", file_name)
        m["jenis"] = kind
        m["status"] = document_status(file_name)
        # Dipakai Row-Level Security di L6. Ditulis ke metadata saat
        # indexing, BUKAN disisipkan belakangan lewat UPDATE — supaya
        # dokumen yang baru ditambahkan tidak pernah lolos tanpa pemilik.
        m["unit"], m["klasifikasi"] = ownership(file_name)
        # PDF punya "page" dari PyPDFLoader, bernomor mulai 0. Nomor mentah ini
        # sengaja disimpan apa adanya karena evaluasi membandingkannya dengan
        # testset.json; display.lokasi yang mengubahnya jadi nomor cetak saat
        # ditampilkan. Sumber non-halaman (mis. Markdown) dibiarkan None —
        # display.lokasi menampilkan nama bagian untuk itu.
        m.setdefault("page", None)

        file_path = [str(m[k]) for k in PATH_SECTION if m.get(k)]
        if file_path:
            document.page_content = "[" + " > ".join(file_path) + "]\n\n" + document.page_content
        result.append(document)
    return result
