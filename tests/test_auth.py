"""Autentikasi per-user: hash argon2id + penggabungan identitas di login().

Tanpa Oracle. Lapis argon2 diuji langsung (murni kripto); jalur database
di-monkeypatch, jadi kita menguji LOGIKA login (gabung identitas live + peran
dari direktori) tanpa satu pun koneksi.
"""
from __future__ import annotations

import pytest


def test_argon2_roundtrip_dan_salt_acak():
    """hash_password menghasilkan argon2id yang bisa diverifikasi, dan dua hash
    dari sandi SAMA berbeda (salt acak) - bukan SHA-256 polos yang deterministik."""
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    from ragcore.domain import auth

    h1 = auth.hash_password("lab2026")
    h2 = auth.hash_password("lab2026")
    assert h1.startswith("$argon2id$")
    assert h1 != h2                                   # salt acak
    PasswordHasher().verify(h1, "lab2026")            # tak melempar = cocok
    with pytest.raises(VerifyMismatchError):
        PasswordHasher().verify(h1, "salah")


def test_login_pakai_verifier_palsu_identitas_dari_registry(monkeypatch):
    """Jalur tes (verifier disuntik): identitas dari REGISTRY, sandi divalidasi
    verifier. Ini yang dipakai conftest supaya seluruh suite hermetis."""
    from ragcore.domain import users

    users.set_verifier(lambda nip, pw: pw == "lab2026" and nip in users.REGISTRY)
    try:
        p = users.login("NCS-0001", "lab2026")
        assert p is not None and p.name == "Chandra Halim"
        assert users.login("NCS-0001", "salah") is None
        assert users.login("NCS-XXXX", "lab2026") is None
    finally:
        users.set_verifier(None)


def test_login_jalur_db_gabung_identitas_live_peran_dari_direktori(monkeypatch):
    """Jalur sungguhan (tanpa verifier): auth.verify di-monkeypatch mengembalikan
    identitas 'live'. login HARUS memakai nama/unit dari situ, tetapi PERAN dari
    REGISTRY - karena peran tak bisa disimpulkan dari karyawan."""
    from ragcore.domain import auth, users

    users.set_verifier(None)   # pastikan jalur database
    # Identitas 'dari karyawan' sengaja beda nama, untuk membuktikan ia dipakai.
    monkeypatch.setattr(auth, "verify",
                        lambda nip, pw: auth.Identitas("Nama Live", "Divisi TI")
                        if (nip == "NCS-0031" and pw == "benar") else None)
    p = users.login("NCS-0031", "benar")
    assert p is not None
    assert p.name == "Nama Live"        # identitas LIVE dari karyawan
    assert p.unit == "Divisi TI"
    assert p.role == users.REGISTRY["NCS-0031"].role   # peran dari direktori
    assert users.login("NCS-0031", "salah") is None


def test_login_db_nip_asing_boleh_masuk_peran_staf(monkeypatch):
    """NIP yang ada di karyawan tapi belum di REGISTRY: boleh masuk, peran STAF
    (fail-closed) - bukan menolak, bukan naik peran."""
    from ragcore.domain import auth, users

    users.set_verifier(None)
    monkeypatch.setattr(auth, "verify",
                        lambda nip, pw: auth.Identitas("Ratna Kusuma", "Direksi")
                        if nip == "NCS-0002" else None)
    p = users.login("NCS-0002", "apa pun")
    assert p is not None and p.name == "Ratna Kusuma"
    assert p.role == users.STAFF_ROLE


def test_tak_ada_sandi_hardcode_di_users():
    """Jaring pengaman: pastikan sandi lab lama tak balik lagi ke kode."""
    import inspect

    from ragcore.domain import users

    src = inspect.getsource(users)
    assert "lab2026" not in src
    assert "_LAB_PASSWORD" not in src
    assert "sha256" not in src
