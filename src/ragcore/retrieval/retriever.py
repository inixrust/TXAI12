"""Tiga cara mencari, sengaja dipisah agar bisa dibandingkan satu sama lain
di modul B6:

    search_vector(t)   pencarian semantik saja        — dasar
    search_hybrid(t)   vektor + BM25 digabung RRF     — memperbaiki CAKUPAN
    retrieve_best(t) hybrid + penyusunan ulang      — memperbaiki KETEPATAN

Ketiganya menerima `filters` dengan aturan yang sama (lihat filters.py):
None berarti filters bawaan, `{}` berarti tanpa filters sama sekali.
"""
from __future__ import annotations

from ragcore.domain import Document

from .. import config
from ..model import get_reranker
from .abbreviations import expand
from .filters import Filters, default_filter, for_store, passes_access, passes_filter
from .fusion import rrf
from .sources import source


def search_vector(
    question: str, k: int | None = None, filters: Filters | None = None,
    person=None,
) -> list[Document]:
    """Pencarian semantik murni — dasar pembanding untuk dua cara lainnya."""
    return source(person).store.similarity_search(
        expand(question),
        k=k or config.N_CANDIDATES,
        filter=for_store(default_filter(filters)),
    )


def search_hybrid(question: str, filters: Filters | None = None,
                person=None, self_query: bool | None = None) -> list[Document]:
    """Vektor + BM25. Memperbaiki CAKUPAN — memunculkan dokumen yang
    sebelumnya tidak pernah terambil, misalnya yang memuat nomor surat.

    `mandiri=True` menyalakan self-query: filters tambahan diturunkan dari
    pertanyaan itu sendiri (jenis dokumen, rentang masa berlaku). Bawaannya
    mengikuti config.SELF_QUERY karena ia menambah satu panggilan LLM di
    depan setiap pencarian — 8 sampai 16 detik pada qwen3:4b, dan itu harga
    yang tidak selalu sepadan untuk pertanyaan yang memang tanpa batasan.
    """
    retriever = source(person)
    query = expand(question)
    filters = default_filter(filters)

    # Self-query. Urutan penggabungan MENENTUKAN, dan sengaja dibuat begini:
    # filters dari pertanyaan dipasang LEBIH DULU, lalu filters identitas
    # ditimpakan di atasnya. Dengan begitu, apa pun yang berhasil diselundupkan
    # ke dalam hasil self-query tidak akan pernah menggeser kewenangan.
    #
    # self_query.bersihkan() sudah membuang field kewenangan, jadi ini
    # lapis kedua untuk hal yang sama - dan itu memang disengaja. Satu-satunya
    # pembatas yang layak dipercaya adalah yang tetap berlaku ketika lapis di
    # atasnya gagal.
    sejak = sampai = None
    if config.SELF_QUERY if self_query is None else self_query:
        from .self_query import extract, split_filters

        setara, (sejak, sampai) = split_filters(extract(question))
        if setara:
            filters = {**setara, **filters}

    vector_result = retriever.store.similarity_search(
        query, k=config.N_CANDIDATES, filter=for_store(filters)
    )

    # BM25 tidak mengenal filters metadata, jadi disaring manual di sini.
    # Kalau langkah ini terlupa, dokumen yang dicabut akan bocor lewat jalur
    # leksikal meski jalur vektor sudah disaring — kegagalan senyap yang khas.
    # DUA filters, dan yang kedua tidak boleh dilewatkan.
    #
    # passes_filter : filters aplikasi yang bisa disetel (status, klasifikasi).
    # lolos_akses  : penegakan hak akses. BM25 tidak lewat basis data sama
    #                sekali, jadi RLS tidak menjangkaunya — lihat filters.py.
    #                Tanpa baris ini, sisi leksikal membocorkan dokumen unit
    #                lain sementara sisi vektornya aman.
    bm25_result = [d for d in retriever.bm25.invoke(query)
                  if passes_filter(d, filters) and passes_access(d, person)]

    result = rrf([vector_result, bm25_result])

    # Batas tanggal diterapkan SETELAH penggabungan, bukan sebelum: filters
    # PGVectorStore dan Chroma di lab ini hanya menangani kesetaraan, sehingga
    # rentang tidak bisa dititipkan ke storage. Lihat self_query.
    if sejak or sampai:
        from .self_query import within_range

        result = [d for d in result if within_range(d, sejak, sampai)]
    return result


def retrieve_best(
    question: str, k: int | None = None, filters: Filters | None = None,
    person=None, self_query: bool | None = None,
) -> list[Document]:
    """Hybrid + penyusunan ulang. Memperbaiki KETEPATAN — menaikkan chunks
    yang paling relevan ke urutan atas. Bila reranker tidak tersedia, hasil
    hybrid dikembalikan apa adanya."""
    k = k or config.N_FINAL
    kandidat = search_hybrid(question, filters=filters, person=person,
                           self_query=self_query)
    if not kandidat:
        return []

    penyusun = get_reranker()
    if penyusun is None:
        return kandidat[:k]

    value = penyusun.predict([(question, d.page_content) for d in kandidat])
    urut = sorted(zip(kandidat, value, strict=False), key=lambda pasangan: pasangan[1], reverse=True)
    return [document for document, _ in urut[:k]]
