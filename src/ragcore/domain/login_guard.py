"""Pembatas percobaan login: throttle + lockout untuk meredam brute-force.

Sandi kini di-hash argon2id - lambat & mahal per-coba (lihat domain/auth.py).
Tetapi 'lambat' saja tak cukup: tanpa batas, penyerang tetap bisa mencoba tanpa
henti. Ini menambah lockout sementara setelah beberapa kegagalan berturut.

BATAS JUJUR (dibaca sebelum dipakai di produksi):
  - State DI MEMORI proses. Untuk satu node (lab, satu container) memadai. Untuk
    banyak replika, pindahkan ke penyimpanan bersama (Redis/DB) - antarmukanya
    sengaja kecil supaya mudah ditukar.
  - Kunci per-NIP: melindungi AKUN dari penebakan sandi. Pembatasan per-IP
    (mencegah satu penyerang menghantam banyak akun) idealnya di edge -
    Caddy/WAF - bukan di sini.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

# Ambang & durasi bisa ditimpa lewat env. Default: 5 gagal dalam 15 menit ->
# terkunci 15 menit. argon2 sudah memperlambat tiap coba; ini menutup sisanya.
_MAKS_GAGAL = int(os.getenv("LOGIN_MAKS_GAGAL", "5"))
_LOCKOUT_DETIK = int(os.getenv("LOGIN_LOCKOUT_DETIK", "900"))
_JENDELA_DETIK = int(os.getenv("LOGIN_JENDELA_DETIK", "900"))


@dataclass
class _Entri:
    gagal: int = 0
    pertama: float = 0.0
    terkunci_sampai: float = 0.0


class LoginGuard:
    """Pelacak percobaan gagal per-kunci, aman-thread (Streamlit rerun + API)."""

    def __init__(self, maks_gagal: int = _MAKS_GAGAL,
                 lockout: int = _LOCKOUT_DETIK, jendela: int = _JENDELA_DETIK):
        self._maks = maks_gagal
        self._lockout = lockout
        self._jendela = jendela
        self._data: dict[str, _Entri] = {}
        self._lock = threading.Lock()
        self._now = time.monotonic          # bisa diganti di tes (jam palsu)

    def terkunci(self, key: str) -> int:
        """Detik lockout yang tersisa; 0 bila tidak terkunci."""
        with self._lock:
            e = self._data.get(key)
            if not e:
                return 0
            sisa = e.terkunci_sampai - self._now()
            return int(sisa) + 1 if sisa > 0 else 0

    def catat_gagal(self, key: str) -> int:
        """Catat satu kegagalan; kembalikan detik lockout bila memicu, else 0."""
        with self._lock:
            now = self._now()
            e = self._data.setdefault(key, _Entri())
            if e.gagal == 0 or now - e.pertama > self._jendela:
                e.gagal = 0                  # jendela habis -> mulai hitung ulang
                e.pertama = now
            e.gagal += 1
            if e.gagal >= self._maks:
                e.terkunci_sampai = now + self._lockout
                e.gagal = 0                  # hitung ulang setelah lockout
                return self._lockout
            return 0

    def catat_sukses(self, key: str) -> None:
        """Login berhasil menghapus riwayat gagal akun itu."""
        with self._lock:
            self._data.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._data.clear()


# Satu instance dipakai bersama seluruh proses.
GUARD = LoginGuard()


def guarded_login(nip: str, password: str) -> tuple[object | None, int]:
    """Login dengan lockout. Kembalikan (person, detik_terkunci).

    detik_terkunci > 0 berarti DITOLAK karena terlalu banyak percobaan - baik
    saat sudah terkunci maupun saat kegagalan ini yang memicunya. person None
    dengan detik_terkunci 0 berarti sandi salah biasa.
    """
    from ragcore.domain.users import login

    key = (nip or "").strip().upper()
    sisa = GUARD.terkunci(key)
    if sisa > 0:
        return None, sisa
    person = login(nip, password)
    if person is None:
        return None, GUARD.catat_gagal(key)
    GUARD.catat_sukses(key)
    return person, 0
