"""Tipe data domain — satu-satunya pintu ke tipe langchain yang mengalir
lewat tanda tangan fungsi di seluruh aplikasi.

KENAPA LAPISAN INI ADA (anti-corruption layer).

`Document` dari langchain mengalir ke belasan modul: loader menghasilkannya,
pemotong membaginya, retriever mengembalikannya, generator memakainya. Selama
tiap modul mengimpornya langsung dari `langchain_core.documents`, satu
perubahan jalur impor di pustaka itu merembet ke belasan berkas sekaligus.

Modul ini menjadi SATU titik itu. Kode aplikasi menulis:

    from ragcore.domain import Document

dan langchain menjadi detail yang bisa ditukar dari sini saja - bukan fondasi
yang menembus ke mana-mana. Kalau suatu hari tipe ini diganti (pustaka lain,
atau tipe milik sendiri), yang berubah hanya berkas ini.

Sengaja HANYA tipe data yang diekspor ulang, bukan konstruktor berat. Model
dibangun di `model/provider.py`, storage di `storage/`, graf di `flow/` -
masing-masing sudah menjadi seam-nya sendiri. Menyeret semuanya ke sini justru
membuat satu god-module baru, persis yang baru saja dibongkar dari config.
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.messages import (
    AIMessage,
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
