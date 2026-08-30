"""Pustaka lab RAG PT Nusantara Cipta Solusi (TX-AI11).

Susunan paket mengikuti tahapan pipeline, bukan ukuran berkas:

    config        semua setelan — satu-satunya tempat mengubah perilaku
    errors         kelas errors lab, agar penanganan errors bisa spesifik
    fingerprint    catatan DENGAN APA indeks dibangun (pelajaran F3)
    display      pencetak chunks & keterangan letak untuk citation
    model/        pembuat objek embedding, LLM, reranker (+ mode tiruan)
    indexing/ muat -> potong -> embed -> simpan
    retrieval/  vektor + BM25 -> RRF -> susun ulang
    generation/ konteks -> prompt -> jawaban ber-citation
    agen/         alat + lingkaran agent (modul A2/A6)
    evaluasi/     set uji dan metrik
    doctor      pemeriksaan kesiapan (dipakai check.py)
    ui     aplikasi Streamlit (modul A5)
    perintah/     titik masuk baris perintah; berkas di src/ hanya pembungkus

Berkas di `src/` (check.py, index.py, search.py, ...) sengaja dibiarkan tipis:
semua perintah di PANDUAN-PESERTA.md tetap berjalan apa adanya, sementara
logikanya bisa diimpor dan diuji tanpa menjalankan skrip.

Modul ini sengaja TIDAK mengimpor apa pun secara langsung. `check.py` harus
tetap bisa berjalan di mesin yang paketnya belum lengkap — dan itu mustahil
bila mengimpor `ragcore` ikut menarik langchain.
"""

__version__ = "1.0.0"
