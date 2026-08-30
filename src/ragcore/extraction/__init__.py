"""Ekstraksi dokumen hasil pindaian (TX-AI12 Hari 1).

  vlm.py      - membaca halaman tanpa lapisan teks memakai model vision (L3)
  mutu.py     - tiga lapis pemeriksaan hasil ekstraksi (L4)
  table_chunker.py - pemotongan yang tidak memenggal tabel dari judul kolomnya (L4)
"""
from ragcore.extraction.quality import (
    check_structural,
    cross_check,
    quality_report,
)
from ragcore.extraction.table_chunker import chunk_table_aware
from ragcore.extraction.vlm import extract_with_vlm, load_pdf_smart

__all__ = [
    "check_structural",
    "chunk_table_aware",
    "cross_check",
    "extract_with_vlm",
    "load_pdf_smart",
    "quality_report",
]
