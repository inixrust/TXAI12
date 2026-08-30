"""Bandingkan empat pendekatan RAG tanpa embedding (L11).

    python -m ragcore.commands.compare
    python -m ragcore.commands.compare leksikal konteks_penuh
"""
from __future__ import annotations

import sys

from ragcore.vectorless.compare import APPROACH, compare_all

from ._args import wants_help


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if wants_help(argv, __doc__):
        return 0
    dipilih = tuple(a for a in argv if a in APPROACH) or APPROACH
    salah = [a for a in argv if a not in APPROACH]
    if salah:
        print(f"  Tidak dikenal: {salah}. Pilihan: {', '.join(APPROACH)}")
        return 1
    compare_all(approach=dipilih)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
