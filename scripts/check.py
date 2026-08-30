#!/usr/bin/env python
"""Jalankan pemeriksaan yang sama dengan CI, secara lokal - sebelum menyerahkan.

    python scripts/check.py

Menjalankan ruff lalu tes cepat (yang bertanda `lambat` dilewati - itu butuh
Ollama/Postgres/Oracle hidup). Lintas-platform: Windows, macOS, Linux. Keluar
dengan kode bukan-nol bila ada yang gagal, jadi bisa dipakai sebagai git hook.

Ini bukan pengganti CI, melainkan CARA MENJALANKAN HAL YANG SAMA lebih dulu -
supaya kegagalan ketahuan di mesin sendiri, bukan setelah push.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent

# Memakai `python -m` supaya menemukan ruff/pytest lewat interpreter yang
# sedang dipakai - tidak bergantung pada keduanya ada di PATH.
CHECKS = [
    ("ruff lint", [sys.executable, "-m", "ruff", "check", "src", "tests", "apps"]),
    ("tes cepat", [sys.executable, "-m", "pytest", "tests", "-q",
                   "-m", "not lambat"]),
]


def main() -> int:
    env = {**os.environ, "PYTHONPATH": "src"}
    env.setdefault("STORAGE", "chroma")

    gagal = []
    for nama, cmd in CHECKS:
        print(f"\n=== {nama}: {' '.join(cmd)} ===")
        hasil = subprocess.run(cmd, cwd=LAB, env=env)
        if hasil.returncode != 0:
            gagal.append(nama)

    print("\n" + "=" * 50)
    if gagal:
        print("GAGAL:", ", ".join(gagal))
        return 1
    print("SEMUA LULUS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
