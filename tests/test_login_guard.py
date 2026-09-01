"""Lockout login: throttle brute-force sebagai logika MURNI, dengan jam palsu.

Tak ada tidur sungguhan, tak ada layanan - jam disuntik supaya lockout & habisnya
jendela bisa diuji seketika.
"""
from __future__ import annotations

from ragcore.domain.login_guard import GUARD, LoginGuard, guarded_login


def _guard_jam():
    g = LoginGuard(maks_gagal=3, lockout=60, jendela=30)
    t = {"now": 1000.0}
    g._now = lambda: t["now"]
    return g, t


def test_lockout_setelah_ambang_gagal():
    g, t = _guard_jam()
    assert g.catat_gagal("NCS-0001") == 0        # 1
    assert g.catat_gagal("NCS-0001") == 0        # 2
    assert g.catat_gagal("NCS-0001") == 60       # 3 -> memicu lockout
    assert g.terkunci("NCS-0001") > 0            # sekarang terkunci


def test_lockout_habis_setelah_durasi():
    g, t = _guard_jam()
    for _ in range(3):
        g.catat_gagal("NCS-0001")
    assert g.terkunci("NCS-0001") > 0
    t["now"] += 61                               # lewat masa lockout
    assert g.terkunci("NCS-0001") == 0


def test_sukses_menghapus_riwayat():
    g, t = _guard_jam()
    g.catat_gagal("NCS-0001")
    g.catat_gagal("NCS-0001")
    g.catat_sukses("NCS-0001")                   # reset
    assert g.catat_gagal("NCS-0001") == 0        # mulai dari nol lagi
    assert g.catat_gagal("NCS-0001") == 0


def test_jendela_gagal_kedaluwarsa():
    """Kegagalan yang berjauhan (di luar jendela) tak menumpuk jadi lockout."""
    g, t = _guard_jam()
    g.catat_gagal("NCS-0001")
    t["now"] += 31                               # lewat jendela 30 dtk
    g.catat_gagal("NCS-0001")                    # dihitung sebagai yang pertama
    t["now"] += 31
    assert g.catat_gagal("NCS-0001") == 0        # belum 3 berturut dalam jendela


def test_akun_terpisah_tak_saling_mengunci():
    g, t = _guard_jam()
    for _ in range(3):
        g.catat_gagal("NCS-0001")
    assert g.terkunci("NCS-0001") > 0
    assert g.terkunci("NCS-0023") == 0           # akun lain tak terpengaruh


def test_guarded_login_mengunci_lalu_menolak_sandi_benar_sekalipun():
    """Integrasi dengan login sungguhan (verifier palsu dari conftest = lab2026):
    setelah cukup gagal, bahkan sandi BENAR ditolak selama terkunci."""
    GUARD.reset()
    GUARD._maks = 3                              # perkecil ambang untuk tes cepat
    try:
        for _ in range(3):
            person, terkunci = guarded_login("NCS-0001", "salah")
        assert terkunci > 0                       # percobaan ke-3 memicu lockout
        # Sandi benar pun ditolak selama terkunci:
        person, terkunci = guarded_login("NCS-0001", "lab2026")
        assert person is None and terkunci > 0
    finally:
        GUARD.reset()
        GUARD._maks = 5


def test_guarded_login_sukses_normal_tak_terkunci():
    person, terkunci = guarded_login("NCS-0001", "lab2026")
    assert person is not None and terkunci == 0
