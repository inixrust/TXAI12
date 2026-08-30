"""Perluasan query lewat daftar singkatan.

Cara perluasan query termurah yang ada, dan paling berdampak untuk korpus
organisasi Indonesia. Tidak butuh model, tidak butuh pelatihan — hanya daftar
pasangan istilah. Tambahkan singkatan organisasi Anda di sini.
"""
from __future__ import annotations

ABBREVIATION: dict[str, str] = {
    "sppd": "Surat Perintah Perjalanan Dinas",
    "simpeg": "Sistem Informasi Kepegawaian",
    "sop": "Standar Operasional Prosedur",
    "se": "Surat Edaran",
    "sk": "Surat Keputusan",
    "po": "Purchase Order",
    "nib": "Nomor Induk Berusaha",
    "npwp": "Nomor Pokok Wajib Pajak",
}

# Tanda baca yang dilepas dari ujung kata sebelum dicocokkan.
READ_MARKER = ".,?!"


def expand(question: str) -> str:
    """Tambahkan kepanjangan singkatan yang muncul di pertanyaan."""
    word = {k.strip(READ_MARKER).lower() for k in question.split()}
    tambahan = [length for pendek, length in ABBREVIATION.items() if pendek in word]
    return question + (" " + " ".join(tambahan) if tambahan else "")
