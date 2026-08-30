"""Lapisan domain: konsep inti sistem, terpisah dari infrastruktur.

Dulu konsep-konsep ini menganggur di root paket bersama modul infrastruktur
(tracing, log, errors) dan presentasi (ui) - satu namespace tanpa batas yang
menampung apa saja yang tak punya rumah. Sekarang mereka punya rumah:

    types    tipe data framework yang mengalir lewat tanda tangan (Document,
             pesan) - anti-corruption layer ke langchain
    users    identitas, RBAC, dan penyusunan sambungan RLS
    guard    aturan integritas keluaran (kebocoran prompt, sitasi karangan)

types diekspor ulang di sini supaya `from ragcore.domain import Document`
tetap bekerja seperti sebelum domain menjadi paket.
"""
from ragcore.domain.types import (
    AIMessage,
    Document,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

__all__ = [
    "AIMessage",
    "Document",
    "HumanMessage",
    "SystemMessage",
    "ToolMessage",
]
