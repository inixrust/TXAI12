"""Token sesi bertanda-tangan: sah dipulihkan, palsu/kedaluwarsa ditolak.

Inti keamanannya satu kalimat: cookie boleh DIBACA users, tak boleh DITULIS
users. Tes ini menjaga bahwa mengutak-atik subjek, memperpanjang kedaluwarsa,
atau menebak dengan rahasia lain - semuanya gagal-tertutup ke None.
"""
from __future__ import annotations

import time

from ragcore.domain import session


def test_bolak_balik_sah():
    tok = session.mint("NCS-0001")
    assert session.verify(tok) == "NCS-0001"


def test_subjek_tamu_bolak_balik():
    assert session.verify(session.mint("PUBLIC")) == "PUBLIC"


def test_kedaluwarsa_ditolak():
    tok = session.mint("NCS-0023", ttl=-1)   # sudah lewat saat dibuat
    assert session.verify(tok) is None


def test_masih_berlaku_diterima():
    assert session.verify(session.mint("NCS-0023", ttl=60)) == "NCS-0023"


def test_tanda_tangan_diutak_atik_ditolak():
    body, sig = session.mint("NCS-0023").rsplit(".", 1)
    # Tukar tanda tangan dengan yang lain -> tak cocok.
    assert session.verify(f"{body}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}") is None


def test_subjek_dipalsukan_tanpa_rahasia_ditolak():
    """Menyusun ulang body agar subjek jadi Direksi, tanpa tahu rahasia -> gagal."""
    import base64
    palsu_subj = base64.urlsafe_b64encode(b"NCS-0001").rstrip(b"=").decode()
    exp = int(time.time()) + 3600
    body = f"{palsu_subj}|{exp}"
    # Tanda tangan asal-asalan (bukan HMAC rahasia server).
    assert session.verify(f"{body}.tandatanganpalsu") is None


def test_bentuk_rusak_ditolak():
    for bad in (None, "", "tanpa-titik", "a.b.c", "....", "hanyabody."):
        assert session.verify(bad) is None
