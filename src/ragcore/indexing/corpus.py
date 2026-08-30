"""Langkah 1-2 pipeline indexing: memuat seluruh dokumen dan memotongnya.

Nama subfolder di documents/ menjadi `jenis` chunks (sop, edaran, notulen) —
dan jenis itulah yang menentukan strategi pemotongan serta ikut tersimpan di
metadata untuk penyaringan di kemudian hari.
"""
from __future__ import annotations

from pathlib import Path

from ragcore.domain import Document

from .. import config
from ..errors import DocumentFolderMissing, EmptyCorpus, UnreadableDocument
from . import loader, tagger

NAME_WIDTH = 44


def load_all(root: Path | str | None = None, quiet: bool = False) -> list[Document]:
    """Baca seluruh dokumen di folder documents/, kembalikan daftar chunks.

    `quiet=True` mematikan laporan per berkas — dipakai bila keluarannya tidak
    perlu dilihat, misalnya di dalam pengujian.
    """
    root = Path(root or config.DOCUMENT)
    if not root.exists():
        raise DocumentFolderMissing(
            f"Folder dokumen tidak ditemukan: {root}\n"
            f"Jalankan skrip ini dari dalam folder lab/src."
        )

    everything: list[Document] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        kind = folder.name

        for file in sorted(folder.rglob("*")):
            if not loader.supported(file):
                continue

            try:
                chunks = loader.read(file, kind)
            except UnreadableDocument as e:
                # Bukan alasan menghentikan seluruh pembangunan indeks: satu
                # berkas hasil pindaian dilewati, sisanya tetap diproses.
                print(f"  LEWATI {e}")
                continue

            chunks = tagger.add_context(chunks, kind, file.name)
            everything += chunks
            if not quiet:
                print(
                    f"  {file.name:{NAME_WIDTH}s} {len(chunks):3d} potongan "
                    f"({tagger.document_status(file.name)})"
                )

    if not everything:
        raise EmptyCorpus(
            f"Tidak ada dokumen terbaca di {root}.\n"
            f"Pastikan ada berkas .pdf atau .md di dalam subfolder."
        )
    if not quiet:
        print(f"  {'TOTAL':{NAME_WIDTH}s} {len(everything):3d} potongan")
    return everything
