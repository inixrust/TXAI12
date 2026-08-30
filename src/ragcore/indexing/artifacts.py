"""Artefak indeks: basis vektor Chroma dan chunks tersimpan untuk BM25.

Semua sentuhan ke berkas indeks dikumpulkan di sini. Modul retrieval cukup
meminta "buka indeks" tanpa tahu di folder mana, dengan nama koleksi apa, atau
bahwa BM25 memerlukan berkas chunks.json terpisah.
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Sequence

from langchain_chroma import Chroma

from ragcore.domain import Document

from .. import config
from ..errors import IndexNotBuilt
from ..model import get_embedding


def delete_index() -> bool:
    """Hapus folder indeks. Kembalikan True bila memang ada yang dihapus."""
    if not config.INDEX.exists():
        return False
    shutil.rmtree(config.INDEX)
    return True


def create_index(chunks: Sequence[Document]) -> Chroma:
    """Buat embedding seluruh chunks dan simpan ke basis vektor."""
    return Chroma.from_documents(
        documents=list(chunks),
        embedding=get_embedding(),
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.INDEX),
    )


def open_index() -> Chroma:
    """Buka indeks yang sudah dibangun."""
    if not config.INDEX.exists():
        raise IndexNotBuilt(
            # Perintah di pesan errors HARUS bisa disalin-tempel dari
            # tempat peserta berada, yaitu akar lab. "python index.py"
            # hanya jalan dari dalam src/, dan pesan errors justru dibaca
            # ketika seseorang sudah tersesat - bukan saat ia sedang
            # cermat membaca README.
            "Indeks belum dibangun.\n"
            "Jalankan lebih dulu dari akar lab:\n"
            "  python -m ragcore.commands.index"
        )
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embedding(),
        persist_directory=str(config.INDEX),
    )


def vector_count(store: Chroma) -> int:
    """Banyaknya vektor tersimpan.

    Memakai atribut privat `_collection` — satu-satunya cara menghitungnya di
    versi langchain-chroma saat ini. Dikurung di satu fungsi supaya kalau API
    itu berubah, hanya baris ini yang perlu diperbaiki.
    """
    return store._collection.count()


def save_chunks(chunks: Sequence[Document]) -> None:
    """Simpan chunks untuk BM25.

    BM25 bekerja di memori dan tidak membaca dari vector store, jadi
    potongannya disimpan terpisah. Tanpa ini, pencarian hybrid harus memuat
    ulang seluruh PDF setiap kali dijalankan.

    JSON, BUKAN pickle. pickle.load() menjalankan kode apa pun yang tertanam
    di dalam berkasnya - berkas yang bisa ditulis proses lain menjadi jalan
    eksekusi kode. Untuk data yang HANYA berisi teks dan metadata sederhana,
    itu risiko tanpa imbalan; JSON membawa isi yang sama tanpa bisa
    menjalankan apa pun, dan tahan dibaca lintas versi Python maupun pustaka.
    """
    payload = [{"page_content": d.page_content, "metadata": d.metadata}
               for d in chunks]
    config.CHUNKS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def load_chunks() -> list[Document]:
    """Baca chunks yang disimpan saat indeks dibangun. Dibutuhkan BM25."""
    if not config.CHUNKS_FILE.exists():
        raise IndexNotBuilt(
            f"Berkas {config.CHUNKS_FILE.name} tidak ada.\n"
            "Jalankan lebih dulu dari akar lab:\n"
            "  python -m ragcore.commands.index"
        )
    try:
        payload = json.loads(config.CHUNKS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # Berkas pickle lama (.pkl) atau rusak: minta bangun ulang, jangan
        # mencoba membacanya sebagai pickle - itu justru lubang yang ditutup.
        raise IndexNotBuilt(
            f"{config.CHUNKS_FILE.name} bukan JSON yang sah ({type(e).__name__}). "
            "Kemungkinan berkas format lama. Bangun ulang:\n"
            "  python -m ragcore.commands.index --ulang"
        ) from e
    return [Document(page_content=row["page_content"],
                     metadata=row.get("metadata") or {}) for row in payload]
