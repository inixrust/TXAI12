"""Token sesi login yang DITANDATANGANI — supaya refresh tidak mengeluarkan user.

MASALAH YANG DIPECAHKAN. st.session_state Streamlit hilang saat halaman
di-refresh (ia terikat pada koneksi websocket, bukan pada browser). Menyimpan
identitas di cookie mengembalikannya - TETAPI cookie yang bisa dibaca users
juga bisa DITULIS users. Cookie polos berisi `nip=NCS-0001` bukan sesi, itu
undangan: siapa pun menyetelnya dan menjadi Direksi.

KENAPA HMAC. Token di sini = `subjek|kedaluwarsa` ditambah tanda tangan
HMAC-SHA256 memakai rahasia server. Mengubah subjek atau memperpanjang
kedaluwarsa mengubah tanda tangannya, dan tanpa rahasia server tanda tangan
yang cocok tidak bisa dibuat. Jadi cookie boleh dibaca, tak boleh dipalsukan -
sama seperti pola cookie sesi yang ditandatangani di kerangka kerja dewasa.

YANG TIDAK dijamin di sini: kerahasiaan (token terbaca di browser) dan
pencabutan sebelum kedaluwarsa. Untuk lab keduanya cukup; untuk produksi,
cookie httpOnly + daftar-cabut sisi server adalah langkah berikutnya. Batas
itu disebut supaya tidak disangka lebih dari yang ia berikan.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from .. import config


def _b64(raw: bytes) -> str:
    """base64url tanpa padding — aman sebagai nilai cookie."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(body: str) -> str:
    mac = hmac.new(config.SESSION_SECRET.encode(), body.encode(),
                   hashlib.sha256)
    return _b64(mac.digest())


def mint(subject: str, ttl: int | None = None) -> str:
    """Buat token untuk `subject` (NIP atau penanda tamu), berlaku `ttl` detik.

    `subject` datang dari identitas yang SUDAH terverifikasi (login berhasil,
    atau pilihan tamu) - fungsi ini menandatangani, bukan mengautentikasi.
    """
    exp = int(time.time()) + int(config.SESSION_TTL if ttl is None else ttl)
    body = f"{_b64(subject.encode())}|{exp}"
    return f"{body}.{_sign(body)}"


def verify(token: str | None) -> str | None:
    """Kembalikan subject bila token sah DAN belum kedaluwarsa, selain itu None.

    Gagal-tertutup: bentuk apa pun yang tak dikenal, tanda tangan yang tak
    cocok, atau yang sudah lewat waktu -> None (perlakukan sebagai tak login).
    Perbandingan tanda tangan memakai compare_digest agar tak bocor lewat waktu.
    """
    if not token or token.count(".") != 1:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    if body.count("|") != 1:
        return None
    subj_b64, _, exp_str = body.partition("|")
    try:
        if int(exp_str) < int(time.time()):
            return None
        return _unb64(subj_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
