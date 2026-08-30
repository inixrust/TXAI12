"""python -m ragcore.commands.evaluate — evaluasi retrieval + penyaringan.

    python -m ragcore.commands.evaluate
    python -m ragcore.commands.evaluate --penolakan   (butuh model)

Evaluasi retrieval sengaja TIDAK memanggil model bahasa: cepat, murah,
objektif, dan bisa dijalankan setiap kali ada perubahan setelan.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from .. import config
from ..evaluation import (
    compare_methods,
    evaluate_refusal,
    evaluate_status_filter,
    recall_curve,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate.py", description=__doc__)
    parser.add_argument(
        "--penolakan", action="store_true",
        help="ikut menguji kemampuan menolak — memanggil model, jadi lebih lambat",
    )
    args = parser.parse_args(argv)

    print("Setelan aktif:")
    config.summarize()

    compare_methods()
    # Satu angka menyembunyikan perbedaan metode pada korpus sekecil
    # ini; kurvanya yang menunjukkannya. Lihat recall_curve().
    recall_curve()

    # Cepat dan tanpa model — selalu dijalankan karena inilah bukti terukur B3.
    evaluate_status_filter()

    if args.penolakan:
        evaluate_refusal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
