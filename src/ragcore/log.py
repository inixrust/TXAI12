"""Logging untuk diagnostik operasional — TERPISAH dari keluaran pengguna.

KENAPA ADA PEMISAHAN INI.

Sebagian besar `print()` di lab ini memang untuk peserta: jawaban, sumber,
"jalan pikiran" agent. Itu keluaran PRODUK, dan tetap `print`.

Tetapi peringatan, galat, dan pemberitahuan degradasi bukan keluaran produk -
itu diagnostik OPERATOR. Di kelas, keduanya bercampur di stdout dan tidak
apa-apa. Di produksi tidak: operator perlu level (INFO/WARNING/ERROR), nama
modul asal, dan waktu; ia perlu MENYARING; dan ia tidak boleh menemukan
peringatan sistem berdempet dengan data pengguna di aliran yang sama.

Modul ini memberi diagnostik itu tujuannya sendiri. Di mode lab ia tetap
tampil di stderr dengan format terbaca, jadi peserta tidak kehilangan apa pun;
di produksi ia siap ditangkap, disaring, dan dikorelasikan seperti log biasa.

    from ragcore.log import get_logger
    log = get_logger(__name__)
    log.warning("Server MCP tidak terjangkau (%s)", type(e).__name__)
"""
from __future__ import annotations

import logging
import os

_CONFIGURED = False


def _configure() -> None:
    """Pasang satu handler ke logger akar paket. Idempoten.

    LOG_LEVEL mengatur ambangnya (default INFO). Handler-nya menulis ke
    stderr, BUKAN stdout: stdout milik keluaran produk, dan mencampur
    keduanya persis masalah yang modul ini pisahkan.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("ragcore")
    root.setLevel(level)

    # Jangan menggandakan handler bila host (mis. pytest, Streamlit) sudah
    # memasang miliknya sendiri.
    if not root.handlers:
        handler = logging.StreamHandler()   # stderr
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%H:%M:%S"))
        root.addHandler(handler)

    # Biarkan handler root paket yang menangani; jangan naik ke root global
    # yang mungkin dikonfigurasi pihak lain dengan cara yang tak terduga.
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Logger untuk satu modul. Konfigurasi dipasang saat pertama diminta."""
    _configure()
    return logging.getLogger(name if name.startswith("ragcore") else f"ragcore.{name}")
