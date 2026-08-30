"""Pekerja ingest: ambil tugas dari queue, proses, indeks.

Inilah bagian yang membedakan pipeline batch dari pipeline produksi. Sampai
modul ini, seluruh indexing dijalankan OPERATOR lewat
`commands.index` - satu perintah, satu korpus, satu kali jalan. Di sini
indexing dipicu PENGGUNA dan berjalan di latar, dan itu memunculkan
tiga soal yang tidak pernah ada pada pipeline batch:

  1. Dua pekerja tidak boleh mengambil tugas yang sama  -> SKIP LOCKED
  2. Pekerja yang mati tidak boleh menyandera tugasnya  -> batas macet
  3. Menjalankan ulang tidak boleh menggandakan chunks -> hapus dulu

Nomor 3 yang paling mudah terlewat, dan akibatnya paling sulit dilihat:
indeks yang memuat dua salinan dokumen yang sama tetap menjawab, hanya saja
chunks yang sama muncul dua kali di konteks dan menggeser chunks lain
keluar. Tidak ada errors, dan recall-nya justru terlihat baik.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import traceback
from pathlib import Path

from ragcore.log import get_logger

from .. import config
from . import queue

log = get_logger(__name__)

# Jeda saat queue kosong. Cukup pendek agar terasa responsif di kelas,
# cukup panjang agar tidak menghabiskan CPU yang dibutuhkan model.
SECONDS_DELAY = 3.0


def worker_name() -> str:
    """Penanda pekerja, supaya terlihat siapa memegang tugas mana."""
    return f"{socket.gethostname()}/{os.getpid()}"


def process(task: dict, quiet: bool = False) -> int:
    """Proses satu tugas sampai masuk indeks. Kembalikan jumlah chunks.

    Melempar errors bila gagal - pemanggilnya yang mencatat ke queue.
    """
    from ragcore.domain import Document

    from ..extraction import vlm
    from ..extraction.table_chunker import chunk_table_aware
    from ..indexing import tagger

    file_path = Path(task["jalur"])
    if not file_path.exists():
        raise FileNotFoundError(f"berkas tidak ada lagi: {file_path}")

    # 1. Ekstraksi. muat_pdf_pintar mengalihkan halaman tanpa lapisan teks
    #    ke VLM - jalur yang sama persis dengan Hari 1, termasuk singgahannya.
    if file_path.suffix.lower() == ".pdf":
        # BATAS HALAMAN DIPERIKSA SEBELUM VLM DIPANGGIL, bukan sesudahnya.
        # Ekstraksi memakan sekitar dua menit per halaman; memeriksa setelah
        # selesai berarti biayanya sudah terlanjur dikeluarkan seluruhnya.
        from pypdf import PdfReader

        n = len(PdfReader(str(file_path)).pages)
        if n > config.MAX_UPLOAD_PAGES:
            raise ValueError(
                f"{n} halaman melampaui batas {config.MAX_UPLOAD_PAGES}. "
                f"Pecah dokumennya, atau naikkan MAKS_HALAMAN_UNGGAH bila "
                f"memang disengaja.")
        # Konteks jejak Langfuse untuk ekstraksi VLM: tiap halaman jadi satu
        # jejak "ekstraksi-vlm", dikelompokkan per dokumen (session), dan
        # teratribusi ke NIP pengunggah. Tanpa ini, unggahan diproses tanpa
        # satu pun jejak - lihat _call_vlm dan tracing.flush().
        trace_meta = {"berkas": task["nama_berkas"],
                      "session": f"ingest-{task['id']}",
                      "nip": task.get("pengunggah")}
        page = vlm.load_pdf_smart(file_path, quiet=quiet, trace_meta=trace_meta)
    else:
        page = [Document(page_content=file_path.read_text(encoding="utf-8"),
                            metadata={"page": None})]

    # 2. Pemotongan sadar tabel, lalu penandaan metadata (termasuk tanggal).
    chunks: list = []
    for h in page:
        for section in chunk_table_aware(h.page_content):
            meta = dict(h.metadata)
            meta["source"] = task["nama_berkas"]
            chunks.append(Document(page_content=section, metadata=meta))
    chunks = tagger.add_context(chunks, task["jenis"],
                                    task["nama_berkas"])
    if not chunks:
        raise ValueError("tidak ada teks yang bisa diambil dari berkas ini")

    # KEWENANGAN DARI ANTREAN MENIMPA yang disimpulkan dari nama berkas.
    #
    # add_context() memanggil penanda.kepemilikan(), yang mencocokkan AWALAN
    # nama berkas dengan peta yang dipelihara operator. Untuk korpus kurasi
    # itu benar. Untuk berkas yang diunggah users, nama berkasnya tidak
    # ada di peta mana pun - dan nilai bawaannya `umum`, yang berarti
    # terlihat semua orang.
    #
    # Nilai dari queue ditangkap saat unggah dari identitas pengunggah,
    # dan gagal tertutup (`terbatas`). Ia menang di sini.
    if task.get("unit"):
        for d in chunks:
            d.metadata["unit"] = task["unit"]
    if task.get("klasifikasi"):
        for d in chunks:
            d.metadata["klasifikasi"] = task["klasifikasi"]

    # 3. IDEMPOTENSI. Potongan lama dengan nama berkas yang sama dibuang
    #    lebih dulu. Tanpa langkah ini, mengunggah ulang dokumen yang
    #    direvisi akan MENAMBAH chunks, bukan menggantinya - dan indeks
    #    akan memuat versi lama dan versi baru sekaligus, keduanya berstatus
    #    berlaku, tanpa satu pun tanda bahwa ada yang salah.
    if config.STORAGE == "pgvector":
        from ..storage import pgvector

        dibuang = pgvector.delete_by_source(task["nama_berkas"])
        if dibuang and not quiet:
            print(f"    {dibuang} potongan lama dibuang (unggah ulang)")
        pgvector.insert(chunks)
    else:
        from ..indexing import artifacts

        artifacts.open_index().add_documents(chunks)

    # 4. BM25 hidup dari berkas chunks.json, bukan dari basis data - jadi ia harus
    #    ikut diperbarui di sini. Kalau dilewatkan, dokumen baru dapat
    #    ditemukan lewat jalur vektor tetapi tidak lewat jalur leksikal, dan
    #    hybrid search diam-diam menjadi setengah hybrid.
    _refresh_bm25(chunks, task["nama_berkas"])
    return len(chunks)


def _refresh_bm25(chunks: list, file_name: str) -> None:
    """Segarkan berkas chunks yang dipakai BM25."""
    from ..indexing import artifacts

    # Hanya "berkasnya belum ada" yang boleh dimaafkan. Sebelumnya di sini
    # ada `except Exception`, dan ia menelan NameError dari baris di
    # bawahnya selama berminggu-minggu: gejalanya hilang, crash-nya muncul
    # satu baris kemudian tanpa menyebut asalnya.
    try:
        old = [d for d in artifacts.load_chunks()
                if d.metadata.get("source") != file_name]
    except (FileNotFoundError, EOFError):
        old = []
    artifacts.save_chunks(old + chunks)


def run(sekali: bool = False, quiet: bool = False) -> int:
    """Ambil dan proses tugas sampai queue kosong (atau selamanya).

    `sekali=True` memproses paling banyak satu tugas lalu berhenti - dipakai
    untuk pengujian dan untuk peragaan di kelas.
    """
    saya = worker_name()
    queue.setup()
    if not quiet:
        print(f"  pekerja {saya} siap (Ctrl-C untuk berhenti)")

    processing = 0
    try:
        while True:
            task = queue.claim_one(saya)
            if task is None:
                if sekali:
                    break
                time.sleep(SECONDS_DELAY)
                continue

            if not quiet:
                print(f"  [{task['id']}] {task['nama_berkas']} ...")
            mulai = time.perf_counter()
            try:
                n = process(task, quiet=quiet)
            except Exception as e:
                queue.fail(task["id"], f"{type(e).__name__}: {e}")
                if not quiet:
                    log.error("[%s] tugas GAGAL: %s: %s", task['id'],
                              type(e).__name__, e)
                    traceback.print_exc()
            else:
                queue.finish(task["id"], n)
                if not quiet:
                    print(f"  [{task['id']}] selesai, {n} potongan, "
                          f"{time.perf_counter() - mulai:.0f} detik")
            # Kirim jejak ekstraksi SEKARANG, jangan menunggu batch berikutnya:
            # pekerja latar bisa langsung diam setelah ini, dan jejak halaman
            # terakhir tak boleh menggantung. Lihat tracing.flush().
            from .. import tracing
            tracing.flush()
            processing += 1
            if sekali:
                break
    except KeyboardInterrupt:
        # Tugas yang sedang dipegang tetap berstatus `diproses`. Ia akan
        # diambil kembali oleh pekerja mana pun setelah STUCK_LIMIT_MINUTES -
        # lihat queue.claim_one(). Tidak ada yang perlu dibersihkan di sini.
        if not quiet:
            print(f"\n  pekerja berhenti setelah {processing} tugas.")
    return processing


# --------------------------------------------------- pekerja latar in-process

_bg_lock = threading.Lock()
_bg_thread: threading.Thread | None = None


def _bg_loop() -> None:
    """Loop untuk thread latar. run() sudah menangani galat PER-TUGAS (queue.
    fail); yang ditangkap di sini hanya kegagalan di LUAR loop - misalnya
    Postgres sempat mati saat claim_one - supaya thread tidak berhenti diam.
    Dicatat, jeda, lalu dicoba lagi."""
    while True:
        try:
            run(quiet=True)
        except Exception:
            log.exception("pekerja latar tumbang; mengulang")
        time.sleep(SECONDS_DELAY)


def ensure_background_worker() -> bool:
    """Pastikan ADA tepat satu pekerja latar di proses ini. Idempoten & aman-thread.

    Dititipkan ke proses aplikasi (mis. UI Streamlit) supaya dokumen yang
    diunggah langsung diproses di latar SAMPAI SELESAI - tanpa terminal pekerja
    terpisah. Ini TETAP jalur queue + worker yang sama: claim_one memakai FOR
    UPDATE SKIP LOCKED, jadi pekerja in-process ini aman berdampingan dengan
    pekerja manual mana pun (`python -m ragcore.commands.worker`) - peragaan
    dua-pekerja tetap bisa.

    Aman dipanggil berulang (mis. tiap rerun Streamlit): bila thread-nya masih
    hidup ia tak melakukan apa-apa; bila mati ia menghidupkan lagi (memulihkan
    diri). Kembalikan True bila baru dimulai, False bila sudah ada.
    """
    global _bg_thread
    with _bg_lock:
        if _bg_thread is not None and _bg_thread.is_alive():
            return False
        _bg_thread = threading.Thread(
            target=_bg_loop, name="ingest-bg", daemon=True)
        _bg_thread.start()
        log.info("pekerja ingest latar dimulai (in-process, pid %s)", os.getpid())
        return True
