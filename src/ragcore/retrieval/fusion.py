"""Penggabungan hasil beberapa pencari: Reciprocal Rank Fusion."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from ragcore.domain import Document

from .. import config

# Konstanta peredam RRF. Nilai 60 adalah bawaan dari makalah aslinya: cukup
# besar untuk membuat selisih peringkat teratas tidak terlalu tajam.
SILENCER = 60


def _key(document: Document) -> tuple[object, object, str]:
    """Identitas satu chunks.

    Memakai hash ISI PENUH, bukan 60 karakter pertama. Karena jalur judul
    ditempelkan ke setiap chunks ("[sumber > bab > bagian]"), dua chunks
    berbeda dari bagian yang sama bisa berbagi awalan itu — kalau kunci hanya
    chunks awal, keduanya bertabrakan dan salah satunya hilang diam-diam
    dari hasil.
    """
    return (
        document.metadata.get("source"),
        document.metadata.get("page"),
        hashlib.md5(document.page_content.encode("utf-8")).hexdigest(),
    )


def rrf(
    list_list: Iterable[Sequence[Document]],
    k: int = SILENCER,
    get: int | None = None,
) -> list[Document]:
    """Gabungkan beberapa daftar berperingkat menjadi satu.

    Memakai POSISI, bukan skor, karena skor BM25 (0 sampai belasan) dan skor
    kemiripan kosinus (-1 sampai 1) berada pada skala yang tak sebanding.
    """
    score_value: dict[tuple, float] = {}
    save: dict[tuple, Document] = {}

    for listing in list_list:
        for peringkat, document in enumerate(listing, start=1):
            key = _key(document)
            score_value[key] = score_value.get(key, 0.0) + 1.0 / (k + peringkat)
            save[key] = document

    urut = sorted(score_value, key=score_value.__getitem__, reverse=True)
    return [save[key] for key in urut[: (get or config.N_CANDIDATES)]]
