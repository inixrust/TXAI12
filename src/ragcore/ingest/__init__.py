"""Alur ingest asinkron: unggah -> queue -> pekerja -> indeks.

Sampai modul ini seluruh indexing dijalankan OPERATOR lewat
`commands.index`. Di sini ia dipicu PENGGUNA dan berjalan di latar - dan
itulah perbedaan pipeline batch dari pipeline produksi.

    blob.py    berkas asli disimpan lebih dulu, terpisah dari indeks
    queue.py   tugas di PostgreSQL, diambil dengan FOR UPDATE SKIP LOCKED
    worker.py   proses terpisah: ekstrak -> potong -> indeks
"""
from ragcore.ingest import blob, queue, worker

__all__ = ["blob", "queue", "worker"]
