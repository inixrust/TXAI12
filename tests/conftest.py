"""Konfigurasi pytest bersama.

Autentikasi kini memverifikasi sandi terhadap hash argon2id di Oracle (lihat
domain/auth.py). Tes TIDAK boleh menyentuh Oracle - jadi di sini kita SUNTIK
verifikator palsu yang menerima sandi lab 'lab2026' untuk NIP yang dikenal,
persis seperti IngestService menyuntik blob store palsu. Dengan begitu semua
tes yang login lewat `lab2026` tetap berjalan hermetis, tanpa satu pun diubah,
sementara aplikasi sungguhan tetap memakai jalur database.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _auth_palsu():
    from ragcore.domain import users

    users.set_verifier(lambda nip, pw: pw == "lab2026" and nip in users.REGISTRY)
    try:
        yield
    finally:
        users.set_verifier(None)


@pytest.fixture(autouse=True)
def _reset_login_guard():
    """Lockout login berstate di memori proses - bersihkan antar-tes agar
    kegagalan di satu tes tak menular ke tes lain."""
    from ragcore.domain.login_guard import GUARD

    GUARD.reset()
    yield
    GUARD.reset()
