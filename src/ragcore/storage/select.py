"""Satu pintu ke storage yang sedang dipakai.

Seluruh Hari 2 bertumpu pada satu klaim: yang berubah hanya TEMPAT indeks
disimpan, bukan cara sistem mencarinya. Modul ini yang membuat klaim itu
bisa diuji - set uji yang sama dijalankan dua kali, hanya dengan mengubah
satu variabel lingkungan:

    STORAGE=chroma   python -m ragcore.commands.evaluate
    STORAGE=pgvector python -m ragcore.commands.evaluate

Kalau angkanya jauh berbeda, penyebabnya bukan "pgvector lebih buruk",
melainkan ada yang tidak setara di antara keduanya - dan itu yang dicari.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ragcore import config
from ragcore.domain import Document
from ragcore.log import get_logger

log = get_logger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Yang HARUS disediakan sebuah storage agar pipeline ini bekerja.

    Sebelumnya kontrak ini hanya hidup di dalam docstring: "keduanya
    menyediakan similarity_search() dan as_retriever()". Kalimat itu tidak
    pernah diperiksa siapa pun — dan ternyata tidak akurat: `as_retriever()`
    tidak dipanggil di mana pun, sedangkan `add_documents()` yang benar-benar
    dipakai justru tidak disebut.

    Sengaja SESEMPIT mungkin. Kontrak yang mencantumkan lebih dari yang
    dipakai akan menolak implementasi ketiga yang sebenarnya sudah cukup
    memadai - dan menambah pekerjaan yang tidak menghasilkan apa-apa.
    """

    def similarity_search(self, query: str, k: int = 4,
                          **kwargs: Any) -> list[Document]: ...

    def add_documents(self, documents: list[Document],
                      **kwargs: Any) -> list[str]: ...


def store_name() -> str:
    """Penyimpanan yang sedang aktif, untuk ditampilkan ke peserta."""
    return config.STORAGE.strip().lower()


def open_store(hybrid: bool = True, person=None) -> VectorStore:
    """Kembalikan objek storage sesuai config.STORAGE.

    Keduanya memenuhi VectorStore di atas - itulah yang membuat set uji yang
    sama bisa dijalankan pada kedua storage tanpa mengubah satu baris pun di
    pipeline retrieval.

    `person` (User atau None) menentukan SEBAGAI SIAPA sambungan dibuka.
    Ini hanya berlaku untuk pgvector — Chroma adalah berkas lokal dan tidak
    punya konsep peran sama sekali.

    ITULAH PERBEDAAN YANG SESUNGGUHNYA antara kedua storage, dan alasan
    paling menentukan untuk pindah. Bukan kecepatan, bukan skala: Chroma
    TIDAK BISA menegakkan hak akses, apa pun yang ditulis di aplikasi.
    """
    option = store_name()

    # Impor sengaja ditunda: hanya backend yang BENAR-BENAR dipakai yang
    # dimuat. Menaikkan keduanya ke atas berarti setiap perintah menarik
    # chroma DAN psycopg, termasuk yang tidak menyentuh storage sama sekali.
    if option == "chroma":
        from ragcore.indexing.artifacts import open_index

        if person is not None:
            log.warning("Chroma tidak mengenal hak akses per user - pembatasan "
                        "hanya bergantung pada filter aplikasi, yang berlaku "
                        "hanya pada jalur yang ingat memanggilnya.")
        return open_index()

    if option == "pgvector":
        from ragcore.domain.users import connection_for
        from ragcore.storage import pgvector

        return pgvector.open_store(hybrid=hybrid, url=connection_for(person))

    raise ValueError(
        f"STORAGE='{config.STORAGE}' tidak dikenal. "
        f"Pilihannya: chroma atau pgvector."
    )
