"""Pembantu kecil yang dipakai beberapa perintah."""
from __future__ import annotations

import argparse
from collections.abc import Sequence

# Pertanyaan bawaan bila peserta menjalankan perintah tanpa argumen. Sengaja
# satu pertanyaan yang jawabannya jelas ada di korpus, supaya percobaan
# pertama selalu memperlihatkan sistem yang bekerja.
DEFAULT_QUESTION = "Berapa lama masa percobaan karyawan baru?"


def add_question_arg(parser: argparse.ArgumentParser) -> None:
    """Daftarkan argumen pertanyaan bebas-spasi (boleh tanpa tanda kutip)."""
    parser.add_argument(
        "question",
        nargs="*",
        help=f'pertanyaan Anda (bawaan: "{DEFAULT_QUESTION}")',
    )


def merge_questions(parts: Sequence[str]) -> str:
    """Satukan potongan argumen menjadi satu pertanyaan."""
    return " ".join(parts).strip() or DEFAULT_QUESTION


def wants_help(argv, doc: str) -> bool:
    """Cetak bantuan bila diminta. True berarti pemanggil harus berhenti.

    Untuk perintah yang mengurai argv sendiri, bukan lewat argparse.
    Tanpa ini `evaluate_hybrid --help` MENJALANKAN evaluasi 30 kasus - sekitar
    sembilan puluh menit - karena argumen yang tidak dikenal diabaikan diam-
    diam. Peserta yang sekadar ingin tahu pilihannya justru memicu proses
    terpanjang di seluruh lab.
    """
    if not any(a in ("-h", "--help") for a in argv):
        return False
    print((doc or "").strip())
    return True
