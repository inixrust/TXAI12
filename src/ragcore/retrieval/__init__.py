"""Pipeline retrieval: vektor + BM25 -> RRF -> penyusunan ulang.

    singkatan   perluasan query termurah yang ada
    filters   aturan keras: dokumen dicabut tidak pernah keluar (B3)
    gabung      Reciprocal Rank Fusion
    sumber      indeks + BM25 yang dipakai bersama, dimuat sekali
    pencari     tiga cara mencari, sengaja dipisah agar bisa dibandingkan (B6)

Tiga fungsi utama:

    search_vector(t)   pencarian semantik saja        — dasar
    search_hybrid(t)   vektor + BM25 digabung RRF     — memperbaiki CAKUPAN
    retrieve_best(t) hybrid + penyusunan ulang      — memperbaiki KETEPATAN
"""
from __future__ import annotations

from .abbreviations import ABBREVIATION, expand
from .filters import filter_for
from .fusion import rrf
from .retriever import retrieve_best, search_hybrid, search_vector
from .sources import forget_source

__all__ = [
    "ABBREVIATION",
    "annotations",
    "expand",
    "filter_for",
    "forget_source",
    "retrieve_best",
    "rrf",
    "search_hybrid",
    "search_vector",
]
