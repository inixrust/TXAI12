"""python -m ragcore.commands.index — bangun indeks. `--ulang` untuk membangun dari nol.

Ingat pelajaran F3: mengganti MODEL_EMBEDDING atau ukuran chunks di
config.py mengharuskan indexing diulang. Kalau tidak, sistem tetap
berjalan tanpa errors apa pun — hanya hasil pencariannya yang menjadi acak.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from ..indexing import build


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="index.py", description=__doc__)
    parser.add_argument(
        "--ulang", dest="again", action="store_true",
        help="hapus indeks lama lebih dulu, lalu bangun dari nol",
    )
    parser.add_argument(
        "--tanpa-pindaian", dest="no_scans", action="store_true",
        help="jangan sertakan hasil ekstraksi VLM Hari 1",
    )
    args = parser.parse_args(argv)

    build(again=args.again, include_scans=not args.no_scans)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
