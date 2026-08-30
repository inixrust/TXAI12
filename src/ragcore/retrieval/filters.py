"""Penyaringan metadata — aturan keras modul A4 dan B3.

Aturan yang benar-benar tidak boleh dilanggar ditegakkan di KODE, bukan
dititipkan ke instruksi prompt. Prompt hanyalah harapan; filters adalah
jaminan.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ragcore.domain import Document

from .. import config

Filters = dict[str, Any]


def default_filter(filters: Filters | None) -> Filters:
    """Secara bawaan, dokumen yang dicabut TIDAK PERNAH dikembalikan.

    Aturan pemakaian:
        filters=None   -> filters bawaan, hanya dokumen berstatus berlaku
        filters={}     -> tanpa filters sama sekali (untuk demo di kelas)
        filters={...}  -> filters Anda sendiri
    """
    return {"status": config.ACTIVE_STATUS} if filters is None else filters


def filter_for(person: Any = None) -> Filters:
    """Penyaring untuk seorang users — LAPIS APLIKASI (TX-AI12 L6).

    Di TX-AI11 fungsi ini mengembalikan hal yang sama untuk semua orang dan
    cabang perannya hanya tertulis di docstring sebagai contoh. Sekarang ia
    benar-benar bekerja.

    Kewenangan disaring DI SINI, di lapisan retrieval — bukan dengan
    meminta model "jangan menjawab bila users bukan pimpinan". Prompt
    adalah permintaan; filters adalah jaminan.

    TETAPI PENYARING INI BUKAN PENEGAKAN. Ia berlaku hanya pada jalur yang
    memanggilnya. Yang menegakkan adalah Row-Level Security di basis data,
    yang berlaku pada setiap query termasuk yang lupa menyaring. Keduanya
    sengaja dijalankan bersama: kalau filters ini suatu saat keliru
    dilonggarkan, RLS masih menahan.

    Menerima objek Pengguna maupun dict — ui lama memakai dict.
    """
    from ..domain.users import filter_for as user_filter_for

    if person is None:
        return {"status": config.ACTIVE_STATUS}

    # Bentuk dict lama {"peran": "..."} tetap didukung supaya kode TX-AI11
    # yang diwarisi tidak perlu diubah serentak.
    if isinstance(person, Mapping):
        filters: Filters = {"status": config.ACTIVE_STATUS}
        if person.get("peran") != "pimpinan":
            filters["klasifikasi"] = "umum"
        return filters

    return user_filter_for(person)


def for_chroma(filters: Filters) -> Filters | None:
    """Chroma menolak filters berupa dict kosong dan meminta None.

    Terlihat sepele, tapi ini justru contoh bagus untuk kelas: pustaka sering
    punya aturan tak tertulis yang baru ketahuan saat dijalankan. Karena itu
    kode lab ini diuji, bukan hanya ditulis.
    """
    return filters or None


def for_pgvector(filters: Filters) -> Filters | None:
    """PGVectorStore juga menerima dict, dan bentuk kesetaraan sederhananya
    kebetulan sama dengan Chroma.

    "Kebetulan" itu perlu diucapkan: keduanya menerima {"status": "berlaku"},
    tetapi Chroma menerjemahkannya ke filters bawaannya sendiri sedangkan
    PGVectorStore menyusunnya menjadi klausa WHERE SQL. Yang sama hanya
    bentuk masukannya, bukan cara kerjanya — dan begitu penyaringnya lebih
    rumit daripada kesetaraan ($in, rentang, negasi), keduanya berpisah.

    Fungsi ini sengaja tetap ada meski isinya kembar dengan untuk_chroma:
    ia menandai DI MANA perbedaan itu akan muncul saat penyaringnya
    berkembang, sehingga tidak perlu diburu ke seluruh berkas.
    """
    return filters or None


def for_store(filters: Filters) -> Filters | None:
    """Terjemahkan filters sesuai storage yang sedang aktif."""
    if config.STORAGE.strip().lower() == "pgvector":
        return for_pgvector(filters)
    return for_chroma(filters)


def passes_filter(document: Document, filters: Filters) -> bool:
    """Penyaringan manual untuk BM25, yang tidak mengenal metadata."""
    if not filters:
        return True
    return all(document.metadata.get(k) == v for k, v in filters.items())


def passes_access(document: Document, person: Any) -> bool:
    """Penegakan hak akses untuk jalur yang TIDAK LEWAT BASIS DATA.

    KENAPA INI HARUS ADA — dan kenapa ia mudah sekali terlupakan.

    Row-Level Security menegakkan hak akses pada setiap query ke Postgres.
    Tetapi BM25 tidak bertanya ke Postgres. Ia indeks di memori yang dibangun
    dari `chunks.pkl`, sebuah berkas di cakram tanpa satu pun kebijakan.
    Jadi pada pencarian hybrid, separuh jalurnya terlindungi RLS dan separuh
    lagi TIDAK.

    Terbukti di lab. Dengan filters aplikasi dimatikan:

        search_vector(...)    Andini/Divisi SDM -> 0 chunks terbatas   (aman)
        retrieve_best(...)  Andini/Divisi SDM -> 3 chunks terbatas   (BOCOR)

    Perbedaannya cuma satu: yang kedua ikut memanggil BM25.

    Pelajarannya lebih besar daripada BM25 itu sendiri: SETIAP jalur yang
    memintas basis data membawa serta kewajiban menegakkan aksesnya sendiri.
    Singgahan, indeks di memori, berkas ekspor, salinan untuk analitik —
    semuanya. RLS melindungi basis data, bukan melindungi sistem Anda.

    Penyaring ini TIDAK BISA dimatikan dari ui, berbeda dengan
    filter_for(). Ia bukan kenyamanan; ia pengganti RLS bagi jalur yang
    tak terjangkau RLS.
    """
    if person is None:
        return True     # tanpa identitas = jalur pemeliharaan, bukan layanan

    m = document.metadata
    if m.get("klasifikasi", "umum") == "umum":
        return True
    return m.get("unit") == getattr(person, "unit", None)
