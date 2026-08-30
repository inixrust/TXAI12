"""Pipeline indexing: muat -> potong -> embed -> simpan.

    pemuat       membaca berkas menjadi Document (PDF, Markdown)
    pemotong     strategi chunking per jenis dokumen (pelajaran B2)
    penanda      status dokumen + jalur judul yang ikut di-embed
    korpus       orkestrasi langkah 1-2: load_all()
    storage  artefak indeks: chroma_db/ dan chunks.json
    pembangun    orkestrasi langkah 3-4: bangun()
"""
from __future__ import annotations

from .artifacts import (
    create_index,
    delete_index,
    load_chunks,
    open_index,
    save_chunks,
    vector_count,
)
from .builder import build
from .corpus import load_all

__all__ = [
    "annotations",
    "build",
    "create_index",
    "delete_index",
    "load_all",
    "load_chunks",
    "open_index",
    "save_chunks",
    "vector_count",
]
