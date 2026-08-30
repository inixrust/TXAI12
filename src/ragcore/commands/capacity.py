"""Lembar kerja perencanaan capacity (L13).

    python -m ragcore.commands.capacity --halaman 8412 --detik 9 --porsi 0.35

Isi dengan angka ARSIP ANDA SENDIRI. --detik diukur lebih dulu dengan
menjalankan commands.extract pada beberapa halaman dan mencatat waktunya.
"""
from __future__ import annotations

import sys

from ragcore import capacity as count


def _number(argv, name, default):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return float(argv[i + 1])
    return default


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    count.worksheet(
        page_total=int(_number(argv, "--halaman", 8412)),
        page_per_seconds=_number(argv, "--detik", 9.0),
        scan_ratio=_number(argv, "--porsi", 0.35),
        seconds_per_answer=_number(argv, "--jawaban", 12.0),
        parallel_lanes=int(_number(argv, "--jalur", 1)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
