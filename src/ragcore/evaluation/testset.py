"""Pembacaan set uji dan penyaringan kasus menurut apa yang diujinya.

Nomor halaman di testset.json memakai indeks mulai 0, mengikuti PyPDFLoader.
Halaman pertama bernomor 0 di sini. Jangan bingung bila citation di layar
menyebut "hal. 1" untuk kasus yang di testset.json tertulis halaman 0:
keduanya menunjuk halaman yang sama. Evaluasi memakai indeks mentah, display
memakai nomor cetak — lihat display.lokasi.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .. import config
from ..errors import TestsetMissing

# Satu kasus uji apa adanya dari JSON: tanya, sumber, halaman, jenis, dan
# (opsional) harus_menolak. Dibiarkan sebagai dict supaya berkasnya tetap
# menjadi satu-satunya sumber kebenaran — menambah kolom di JSON tidak
# menuntut perubahan kode di sini.
TestCase = dict[str, Any]

VERSION_KIND = "versi"


def load_testset() -> list[TestCase]:
    """Baca seluruh kasus uji dari testset.json."""
    if not config.TEST_SET.exists():
        raise TestsetMissing(f"Set uji tidak ditemukan: {config.TEST_SET}")
    return json.loads(config.TEST_SET.read_text(encoding="utf-8"))


def retrieval_cases(everything: Sequence[TestCase] | None = None) -> list[TestCase]:
    """Kasus yang punya jawaban benar di dokumen (bukan kasus penolakan)."""
    return [k for k in (everything or load_testset()) if not k.get("harus_menolak")]


def refusal_cases(everything: Sequence[TestCase] | None = None) -> list[TestCase]:
    """Kasus yang jawabannya memang TIDAK ada di korpus."""
    return [k for k in (everything or load_testset()) if k.get("harus_menolak")]


def version_cases(everything: Sequence[TestCase] | None = None) -> list[TestCase]:
    """Kasus bertipe 'versi' — menguji penyaringan status dokumen (B3)."""
    return [k for k in (everything or load_testset()) if k.get("jenis") == VERSION_KIND]


def matches(chunks: Sequence[Any], case: TestCase) -> bool:
    """Apakah salah satu chunks berasal dari sumber dan halaman yang benar?"""
    return any(
        d.metadata.get("source") == case["sumber"]
        and d.metadata.get("page") in case["halaman"]
        for d in chunks
    )
