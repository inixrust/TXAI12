"""Sidik jari indeks: mencatat DENGAN APA indeks dibangun, lalu memastikan
setelan aktif masih cocok sebelum indeks itu dipakai.

Kenapa modul ini ada — inti pelajaran F3:
mengganti model embedding, ukuran chunks, atau berpindah ke/dari mode tiruan
mengharuskan indeks dibangun ulang. Kalau tidak, sistem tetap berjalan TANPA
GALAT tetapi hasil pencariannya menjadi acak. Ini kegagalan senyap yang paling
sulit didiagnosis. Di sini pelajaran itu ditegakkan oleh kode — bukan sekadar
diingatkan lewat komentar yang mudah terlewat.

Letaknya di akar paket, bukan di dalam `indexing/`, karena tiga lapisan
memakainya: pembangunan indeks (menulis), retrieval (memeriksa sebelum
mencari), dan doctor (memeriksa saat `python check.py`). Modul ini juga hanya
memakai pustaka bawaan Python, sehingga aman diimpor check.py.
"""
from __future__ import annotations

import json
import time
from typing import NamedTuple

from . import config


class CheckResult(NamedTuple):
    """Bisa dibongkar seperti tuple: `cocok, pesan = periksa()`."""

    matches: bool
    message: str | None


def write() -> None:
    """Rekam setelan pembangun indeks. Dipanggil setelah indeks dibangun."""
    config.META.write_text(
        json.dumps(
            {
                "model_embedding": config.MODEL_EMBEDDING,
                "ukuran_potongan": config.CHUNK_SIZE,
                "mode_tiruan": config.FAKE_MODE,
                "dibuat": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _diff(tercatat: dict) -> list[str]:
    """Daftar setelan yang berbeda antara indeks dan config aktif."""
    diff: list[str] = []
    if tercatat.get("model_embedding") != config.MODEL_EMBEDDING:
        diff.append(
            f"embedding: indeks '{tercatat.get('model_embedding')}' "
            f"vs config '{config.MODEL_EMBEDDING}'"
        )
    if tercatat.get("ukuran_potongan") != config.CHUNK_SIZE:
        diff.append(
            f"ukuran potongan: indeks {tercatat.get('ukuran_potongan')} "
            f"vs config {config.CHUNK_SIZE}"
        )
    if bool(tercatat.get("mode_tiruan")) != bool(config.FAKE_MODE):
        diff.append(
            f"mode tiruan: indeks {'ya' if tercatat.get('mode_tiruan') else 'tidak'} "
            f"vs sekarang {'ya' if config.FAKE_MODE else 'tidak'}"
        )
    return diff


def check() -> CheckResult:
    """Bandingkan sidik jari indeks dengan setelan aktif.

    Indeks lama tanpa berkas meta dianggap cocok agar tidak menghalangi —
    hanya ketidakcocokan yang benar-benar terdeteksi yang diperingatkan.
    """
    if not config.META.exists():
        return CheckResult(True, None)

    try:
        tercatat = json.loads(config.META.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return CheckResult(True, None)

    diff = _diff(tercatat)
    if not diff:
        return CheckResult(True, None)

    message = (
        "PERINGATAN: indeks dibangun dengan setelan berbeda dari config aktif:\n"
        + "".join(f"    - {b}\n" for b in diff)
        + "  Pencarian akan ACAK tanpa memunculkan errors apa pun (pelajaran F3).\n"
        + "  Bangun ulang lebih dulu dari akar lab:\n"
        + "    python -m ragcore.commands.index --ulang"
    )
    return CheckResult(False, message)
