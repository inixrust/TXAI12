"""python load.py — memuat dan memotong dokumen, lalu tunjukkan satu contoh.

Tidak menyentuh indeks sama sekali. Gunanya melihat HASIL PEMOTONGAN sebelum
menghabiskan waktu membuat embedding — perhatikan awalan
"[sumber > bab > bagian]" pada isi chunks (pelajaran B2).
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from ..indexing import load_all

EXAMPLE_LENGTH = 400
LINE_WIDTH = 66


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="load.py", description=__doc__)
    parser.add_argument(
        "--nomor", dest="number", type=int, default=1,
        help="chunks ke berapa yang ditampilkan sebagai contoh (bawaan: 1)",
    )
    args = parser.parse_args(argv)

    print("Memuat dan memotong dokumen...")
    chunks = load_all()

    index = max(1, min(args.number, len(chunks))) - 1
    example = chunks[index]
    print(f"\nContoh potongan ke-{index + 1} dari {len(chunks)}:")
    print("-" * LINE_WIDTH)
    print(example.page_content[:EXAMPLE_LENGTH])
    print("-" * LINE_WIDTH)
    print("metadata:", example.metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
