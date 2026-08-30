"""Pekerja ingest latar in-process: dititipkan ke proses aplikasi supaya
dokumen yang diunggah diproses SAMPAI SELESAI tanpa terminal pekerja terpisah.

Tes ini TIDAK menyentuh Postgres: loop sesungguhnya diganti dengan yang diam,
jadi yang diuji murni kontraknya - satu pekerja per proses, idempoten, dan
memulihkan diri bila thread-nya mati.
"""
from __future__ import annotations

import threading

from ragcore.ingest import worker


def test_ensure_idempoten_satu_pekerja(monkeypatch):
    started = threading.Event()
    stop = threading.Event()

    def fake_loop():
        started.set()
        stop.wait(5)  # tetap "hidup" selama tes, tanpa menyentuh Postgres

    monkeypatch.setattr(worker, "_bg_loop", fake_loop)
    monkeypatch.setattr(worker, "_bg_thread", None)

    try:
        # Panggilan pertama menghidupkan; kedua melihat thread masih hidup.
        assert worker.ensure_background_worker() is True
        assert started.wait(2), "thread latar tak pernah mulai"
        assert worker.ensure_background_worker() is False
        assert worker._bg_thread is not None and worker._bg_thread.daemon
    finally:
        stop.set()
        worker._bg_thread.join(timeout=2)


def test_ensure_memulihkan_diri_bila_thread_mati(monkeypatch):
    """Bila thread sebelumnya sudah berhenti, panggilan berikutnya
    menghidupkan yang baru - bukan membiarkan proses tanpa pekerja."""
    def fake_loop():
        return  # langsung selesai -> thread mati

    monkeypatch.setattr(worker, "_bg_loop", fake_loop)
    monkeypatch.setattr(worker, "_bg_thread", None)

    assert worker.ensure_background_worker() is True
    worker._bg_thread.join(timeout=2)
    assert not worker._bg_thread.is_alive()
    # Thread mati -> harus menghidupkan lagi.
    assert worker.ensure_background_worker() is True
    worker._bg_thread.join(timeout=2)
