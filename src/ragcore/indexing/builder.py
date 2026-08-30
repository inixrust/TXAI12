"""Langkah 3-4 pipeline indexing: embedding dan storage.

Ingat pelajaran F3: mengganti MODEL_EMBEDDING atau ukuran chunks di config.py
mengharuskan indexing diulang. Kalau tidak, sistem tetap berjalan tanpa
errors apa pun — hanya hasil pencariannya yang menjadi acak.

Sejak TX-AI12 modul ini melayani dua storage. Yang berubah hanya langkah
4; langkah 1-3 identik, dan itu disengaja — supaya perbandingan recall antara
Chroma dan pgvector pada Hari 2 benar-benar membandingkan penyimpanannya,
bukan pipeline yang kebetulan berbeda.
"""
from __future__ import annotations

from typing import Any

from .. import config, fingerprint
from .artifacts import create_index, delete_index, save_chunks, vector_count
from .corpus import load_all
from .corpus_scanned import load_scan


def _build_chroma(chunks) -> Any:
    store = create_index(chunks)
    # Sidik jari: dengan embedding & ukuran chunks apa indeks ini dibuat.
    # Pengambilan dan check.py membacanya untuk menolak ketidakcocokan dini.
    fingerprint.write()
    print(f"\nSelesai. {vector_count(store)} vektor tersimpan "
          f"di {config.INDEX.name}/")
    return store


def _build_pgvector(chunks, again: bool) -> Any:
    from ..storage import pgvector

    print(f"     tabel {config.PG_TABLE} @ {config.EMBEDDING_DIM} dimensi")
    pgvector.setup_table(timpa=again)
    pgvector.insert(chunks)

    # Indeks HNSW dipasang SETELAH penyisipan. Membangunnya lebih dulu berarti
    # setiap penyisipan ikut memperbarui indeks — jauh lebih lambat untuk
    # pemuatan awal, dan tidak ada gunanya karena belum ada yang mencari.
    print("     memasang indeks HNSW")
    try:
        pgvector.create_hnsw_index()
    except Exception as e:
        print(f"     indeks HNSW dilewati ({type(e).__name__}: {e})")
        print("     Pencarian tetap BENAR, hanya memindai seluruh tabel.")

    print("     memasang indeks GIN untuk sisi leksikal")
    try:
        pgvector.install_hybrid_index()
    except Exception as e:
        print(f"     indeks hibrida dilewati ({type(e).__name__}: {e})")

    print(f"\nSelesai. {pgvector.vector_count()} vektor tersimpan "
          f"di tabel {config.PG_TABLE}")

    if again:
        # --ulang MENJATUHKAN tabelnya, dan bersama tabel itu jatuh pula
        # kebijakan RLS beserta GRANT ke peran aplikasi. Postgres tidak
        # memperingatkan apa pun; yang terjadi kemudian adalah peragaan hak
        # akses yang gagal dengan "permission denied" - errors yang menyesatkan
        # karena terdengar seperti masalah izin, padahal tabelnya memang baru.
        print("\n  PERHATIAN: tabel dibuat ulang, kebijakan RLS ikut terhapus.")
        print("  Jalankan lagi:  python -m ragcore.commands.rls --pasang")

    return pgvector.open_store()


def build(again: bool = False, quiet: bool = False,
           include_scans: bool = True) -> Any:
    """Bangun indeks dari nol atau tambahkan ke yang sudah ada.

    `again=True` menghapus indeks lama lebih dulu — inilah yang wajib
    dilakukan setiap kali setelan embedding atau pemotongan berubah.

    `include_scans=True` memasukkan hasil ekstraksi VLM Hari 1. Halaman
    yang sudah pernah diekstrak dibaca dari singgahan, jadi ini murah selama
    berkas *.vlm.txt masih ada.
    """
    from ..storage.select import store_name

    storage = store_name()

    if again and storage == "chroma" and config.INDEX.exists():
        print(f"Menghapus indeks lama di {config.INDEX.name}/ ...")
        delete_index()

    print("\nSetelan aktif:")
    config.summarize()

    print("\n1-2. Memuat dan memotong dokumen")
    chunks = load_all(quiet=quiet)

    if include_scans:
        print("\n1b. Memuat korpus pindaian (hasil ekstraksi Hari 1)")
        scan = load_scan(quiet=quiet)
        if scan:
            chunks = list(chunks) + scan
            print(f"  {'TOTAL setelah pindaian':44s} {len(chunks):3d} potongan")
        else:
            print("  Belum ada hasil ekstraksi. Jalankan commands.extract lebih dulu")
            print("  bila lab Hari 2 harus memuat isi dokumen pindaian.")

    print(f"\n3-4. Membuat embedding dan menyimpan ke {storage}")
    print("     (bagian paling lambat — di laptop tanpa GPU bisa beberapa menit)")

    if storage == "pgvector":
        store = _build_pgvector(chunks, again)
    else:
        store = _build_chroma(chunks)

    # BM25 memakai chunks tersimpan, apa pun storage vektornya.
    save_chunks(chunks)

    # Indeks baru berarti handle pencarian yang tersimpan di memori sudah basi.
    # Diimpor di dalam fungsi supaya indexing tidak bergantung pada
    # retrieval saat impor (keduanya akan saling menunggu).
    from ..retrieval.sources import forget_source

    forget_source()

    print(f"Potongan untuk BM25 tersimpan di {config.CHUNKS_FILE.name}")
    print("\nCatat di catatan proyek Anda:")
    print(f"  penyimpanan     = {storage}")
    print(f"  model embedding = {config.MODEL_EMBEDDING}")
    print(f"  ukuran potongan = {config.CHUNK_SIZE}")
    print("Mengubah salah satunya berarti indeks harus dibangun ulang.")
    return store
