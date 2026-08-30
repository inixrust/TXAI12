"""Membaca satu berkas menjadi chunks Document.

Modul ini hanya tahu cara MEMBACA. Ia tidak mencetak apa pun dan tidak
memutuskan berkas mana yang dilewati — berkas yang tak terbaca dilaporkan
lewat errors `DokumenTakTerbaca`, dan pemanggilnya (korpus.py) yang memilih
mau melewati atau berhenti. Pemisahan ini yang membuat modul bisa diuji tanpa
menangkap keluaran layar.
"""
from __future__ import annotations

import warnings
from pathlib import Path

# langchain-community kini berstatus pemeliharaan; mengimpor PyPDFLoader dapat
# memunculkan peringatan usang yang mengotori layar saat demo di depan kelas.
# Kodenya tetap berjalan. Peringatan disenyapkan HANYA di sekitar baris impor
# ini, sehingga peringatan lain yang muncul kemudian tetap terlihat.
# Sebelum mengajar, cek dokumentasi resmi LangChain: bila PyPDFLoader sudah
# pindah ke paket integrasi tersendiri, ganti impor ini dan requirements.txt.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langchain_community.document_loaders import PyPDFLoader

from ragcore.domain import Document

from ..errors import UnreadableDocument
from .splitters import MARKDOWN_SPLITTER, splitter_for

SUPPORTED_SUFFIX = frozenset({".pdf", ".md"})

# Di bawah jumlah karakter ini, sebuah PDF dianggap tanpa lapisan teks.
# Kebiasaan dari modul F4: PDF hasil pindaian lolos TANPA GALAT dan
# menghasilkan indeks kosong yang membingungkan.
TEXT_THRESHOLD = 50


def supported(file: Path) -> bool:
    """Apakah berkas ini jenis yang bisa dibaca lab?"""
    return file.is_file() and file.suffix.lower() in SUPPORTED_SUFFIX


def _read_pdf(file: Path, kind: str) -> list[Document]:
    page = PyPDFLoader(str(file)).load()

    content = sum(len((h.page_content or "").strip()) for h in page)
    if content < TEXT_THRESHOLD:
        raise UnreadableDocument(file.name)

    for h in page:
        h.metadata["source"] = file.name
    return splitter_for(kind).split_documents(page)


def _read_markdown(file: Path) -> list[Document]:
    text = file.read_text(encoding="utf-8")
    # MarkdownHeaderTextSplitter mengembalikan Document tanpa "source".
    return [
        Document(
            page_content=p.page_content,
            metadata={**p.metadata, "source": file.name},
        )
        for p in MARKDOWN_SPLITTER.split_text(text)
    ]


def read(file: Path, kind: str) -> list[Document]:
    """Baca satu berkas menjadi chunks, sesuai jenis dan formatnya.

    Melempar `DokumenTakTerbaca` bila PDF-nya nyaris tanpa teks.
    """
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(file, kind)
    if suffix == ".md":
        return _read_markdown(file)
    raise ValueError(f"Format tidak didukung: {file.name}")
