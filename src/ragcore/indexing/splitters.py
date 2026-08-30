"""Strategi pemotongan — inti pelajaran B2.

Satu strategi per jenis dokumen. Peraturan berpasal dan notulen rapat butuh
perlakuan berbeda, karena struktur bawaannya memuat makna yang berbeda pula.
"""
from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .. import config


def splitter_for(kind: str) -> RecursiveCharacterTextSplitter:
    """Peraturan dan surat edaran dipotong di batas pasal; sisanya di paragraf.

    `jenis` diambil dari nama subfolder di documents/ (sop, edaran, notulen).
    """
    separator = (
        config.REGULATION_SEPARATOR
        if kind in config.ARTICLED_KINDS
        else config.PROSE_SEPARATOR
    )
    return RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.OVERLAP,
        separators=separator,
    )


# Markdown dipotong menurut headingnya, bukan jumlah karakter: heading adalah
# batas makna yang sudah ditulis penulisnya sendiri.
# strip_headers=False -> heading ikut di teks, dan itu penting untuk embedding.
MARKDOWN_SPLITTER = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "bab"), ("##", "bagian")],
    strip_headers=False,
)
