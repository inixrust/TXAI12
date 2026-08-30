"""Pipeline generation: susun konteks -> prompt -> jawaban ber-citation.

    prompt    kalimat sistem dan perakitan konteks bernomor
    citation    pemeriksaan struktural terhadap penanda sumber
    penjawab  menyatukan retrieval, prompt, dan pemeriksaan
"""
from __future__ import annotations

# Kalimat penolakan diambil dari config, bukan ditulis ulang di sini.
# Ia dicocokkan sebagai teks persis oleh modul evaluasi — kalau ada dua versi
# yang sedikit berbeda, metrik penolakan akan melaporkan nol tanpa ada yang sadar.
from ..config import NOT_FOUND
from .answerer import AnswerResult, answer, compose_answer
from .citation import CitationReport, check_citation
from .prompt import SYSTEM, TEMPLATE, assemble_context

__all__ = [
    "NOT_FOUND",
    "SYSTEM",
    "TEMPLATE",
    "AnswerResult",
    "CitationReport",
    "annotations",
    "answer",
    "assemble_context",
    "check_citation",
    "compose_answer",
]
