"""Autentikasi per-user: hash sandi argon2id di database.

Menggantikan sandi lab yang dulu di-hardcode & DIBAGI (satu sandi untuk semua,
SHA-256 polos di kode). Sekarang tiap user punya hash argon2id sendiri di
ncs.pengguna_auth, dibaca lewat akun HAK-MINIMAL rag_auth yang tak bisa membaca
apa pun selain hash + identitas.

KENAPA MODUL TERPISAH DARI users.py:
users.py adalah IDENTITAS & hak akses - fungsi MURNI, teruji tanpa layanan.
Modul ini menyentuh JARINGAN (Oracle) dan KRIPTO (argon2). Karena itu login()
di users.py memanggil ke sini lewat jalur yang BISA DISUNTIK untuk pengujian
(users.set_verifier) - persis pola IngestService yang menyuntik blob store palsu.

FAIL-CLOSED, bukan fail-safe:
Beda dari loader OpenBao (yang fail-SAFE: rahasia bisa datang dari env bila
OpenBao mati), autentikasi GAGAL-TERTUTUP. Bila Oracle mati / salah konfigurasi,
login DITOLAK - tak ada sumber lain yang aman untuk memverifikasi sandi. Lebih
baik tak seorang pun masuk daripada membuka jalur bypass.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Satu instance PasswordHasher dipakai ulang. Parameter default argon2-cffi
# (time_cost=3, memory_cost=64 MiB, parallelism=4) memenuhi anjuran OWASP;
# naikkan bila perangkat produksi kuat.
_hasher = None


def _ph():
    global _hasher
    if _hasher is None:
        from argon2 import PasswordHasher
        _hasher = PasswordHasher()
    return _hasher


def hash_password(password: str) -> str:
    """String PHC argon2id lengkap (algoritma, parameter, salt, hash) - satu
    kolom, tak perlu salt terpisah. Salt acak per panggilan."""
    return _ph().hash(password)


@dataclass(frozen=True)
class Identitas:
    """Identitas yang diambil LIVE dari ncs.karyawan saat login berhasil."""

    nama: str
    unit: str
    golongan: str = ""     # jenjang kepegawaian -> menentukan peran (users.py)


# user/sandi@dsn - dsn bisa host:port/service (easy-connect).
_DSN = re.compile(r"(?P<user>[^/]+)/(?P<pw>[^@]+)@(?P<dsn>.+)")


def _connect(conn_str: str):
    import oracledb

    m = _DSN.match(conn_str.strip())
    if not m:
        raise ValueError("format koneksi auth tak dikenal (harap user/sandi@dsn)")
    return oracledb.connect(user=m["user"], password=m["pw"], dsn=m["dsn"])


def verify(nip: str, password: str) -> Identitas | None:
    """Kembalikan Identitas bila NIP+sandi cocok, None bila tidak.

    None untuk: NIP tak punya baris sandi, sandi salah, NIP tak ada di karyawan,
    ATAU galat apa pun (Oracle mati, argon2 gagal) - semuanya fail-closed.

    Enumerasi user ditekan: bila NIP tak punya sandi, tetap lakukan satu verify
    'boneka' supaya waktu respons tak membocorkan NIP mana yang ada.
    """
    from argon2.exceptions import Argon2Error

    from ragcore.settings.mcp import ORACLE_CONNECTION_AUTH

    try:
        with _connect(ORACLE_CONNECTION_AUTH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT hash_sandi FROM ncs.pengguna_auth WHERE nip = :1", [nip])
            row = cur.fetchone()
            if not row:
                _verify_boneka(password)      # samakan waktu - anti-enumerasi
                return None
            try:
                _ph().verify(row[0], password)
            except Argon2Error:
                return None
            cur.execute(
                "SELECT nama, unit, golongan FROM ncs.karyawan WHERE nip = :1",
                [nip])
            ident = cur.fetchone()
            if not ident:
                return None
            return Identitas(nama=ident[0], unit=ident[1], golongan=ident[2] or "")
    except Exception as e:
        # Sandi TIDAK ikut dicatat - hanya jenis galatnya, agar operator bisa
        # mendiagnosis (Oracle mati / rag_auth salah) tanpa membocorkan rahasia.
        log.warning("verifikasi sandi gagal-tertutup: %s", type(e).__name__)
        return None


def list_karyawan() -> list[tuple[str, str, str, str]] | None:
    """Semua karyawan (nip, nama, unit, golongan) lewat akun hak-minimal
    rag_auth. None bila Oracle tak terjangkau - pemanggil fallback ke daftar
    di kode. Dipakai UI untuk mengisi dropdown pengguna dari SUMBER SEBENARNYA."""
    from ragcore.settings.mcp import ORACLE_CONNECTION_AUTH

    try:
        with _connect(ORACLE_CONNECTION_AUTH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT nip, nama, unit, golongan FROM ncs.karyawan")
            return [(r[0], r[1], r[2], r[3] or "") for r in cur.fetchall()]
    except Exception as e:
        log.warning("daftar karyawan gagal diambil: %s", type(e).__name__)
        return None


# Hash boneka tetap (sandi acak) untuk menyamakan waktu saat NIP tak ada.
_BONEKA = None


def _verify_boneka(password: str) -> None:
    global _BONEKA
    from argon2.exceptions import Argon2Error

    if _BONEKA is None:
        _BONEKA = hash_password("boneka-anti-enumerasi")
    try:
        _ph().verify(_BONEKA, password)
    except Argon2Error:
        pass
