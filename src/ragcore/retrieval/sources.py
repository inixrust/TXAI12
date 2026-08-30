"""Sumber pencarian: basis vektor + BM25, dimuat sekali lalu dipakai ulang.

Memuat ulang keduanya di setiap pertanyaan berarti membaca kembali chunks
dari cakram dan membangun ulang indeks BM25 — mahal, dan sangat terasa saat
evaluasi memanggil pencarian puluhan kali berturut-turut.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

# BM25Retriever masih berada di langchain-community (status pemeliharaan) dan
# impornya bisa memunculkan peringatan usang. Disenyapkan hanya di baris ini —
# lihat catatan lengkap di indexing/pemuat.py. Kodenya tetap berjalan;
# periksa dokumentasi resmi sebelum mengajar kalau-kalau kelasnya sudah pindah.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langchain_community.retrievers import BM25Retriever

from .. import config, fingerprint
from ..indexing.artifacts import load_chunks


@dataclass(frozen=True)
class SearchSources:
    """Dua pencari yang bekerja berdampingan atas korpus yang sama.

    `basis` tidak lagi selalu Chroma — sejak TX-AI12 ia bisa juga
    PGVectorStore. Yang dituntut dari keduanya cuma satu: menyediakan
    similarity_search(query, k=..., filter=...). Itulah sebabnya sisa
    pipeline tidak perlu tahu yang mana sedang dipakai.
    """

    store: Any
    bm25: BM25Retriever


@lru_cache(maxsize=8)
def source(person=None) -> SearchSources:
    """Siapkan (sekali per users) indeks vektor dan indeks leksikal.

    Di-cache PER PENGGUNA, bukan sekali untuk semua: sambungan pgvector
    membawa identitas unit, jadi dua users berbeda memerlukan dua
    sambungan berbeda. Pengguna adalah dataclass frozen, jadi bisa
    dijadikan kunci cache.

    maxsize=8 memadai untuk kelas. Di sistem sungguhan dengan ratusan
    users, ini diganti pool sambungan yang menyetel GUC per transaksi —
    bukan satu engine per orang.
    """
    from ..storage.select import open_store, store_name

    # Periksa sidik jari indeks SEBELUM memakainya. Kalau indeks dibangun
    # dengan embedding atau ukuran chunks berbeda, hasilnya akan acak
    # tanpa errors — jadi peringatkan sekali, di sini, dengan jelas.
    #
    # Untuk pgvector pemeriksaan ini dilewati: sidik jarinya menempel pada
    # berkas indeks lokal, sedangkan indeks pgvector hidup di basis data
    # yang bisa dibangun dari mesin lain. Padanannya di sana adalah
    # DIMENSI_EMBEDDING, yang ditolak Postgres saat penyisipan bila salah.
    if store_name() == "chroma":
        matches, message = fingerprint.check()
        if not matches:
            print(message)

    store = open_store(person=person)

    # BM25 selalu dibangun dari chunks tersimpan, apa pun storage
    # vektornya — ia bekerja di memori dan tidak pernah membaca vector store.
    bm25 = BM25Retriever.from_documents(load_chunks())
    bm25.k = config.N_CANDIDATES
    return SearchSources(store, bm25)


def forget_source() -> None:
    """Buang sumber yang tersimpan — wajib setelah indeks dibangun ulang."""
    source.cache_clear()
