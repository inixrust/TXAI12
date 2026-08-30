"""python check.py — pemeriksaan kesiapan. JALANKAN INI PALING PERTAMA."""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from ..doctor import run


def main(argv: Sequence[str] | None = None) -> int:
    argparse.ArgumentParser(
        prog="check.py", description=__doc__
    ).parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
