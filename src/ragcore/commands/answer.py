"""python -m ragcore.commands.answer "pertanyaan" — jawaban ber-citation.

Potongan yang diambil ditampilkan LEBIH DULU, di atas jawaban. Itu disengaja:
kebiasaan membaca chunks sebelum membaca jawaban adalah yang memisahkan
orang yang bisa memperbaiki sistem RAG dari orang yang hanya bisa
mengganti-ganti prompt (modul F3).
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from ..generation import answer
from ._args import add_question_arg, merge_questions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="answer.py", description=__doc__)
    add_question_arg(parser)
    parser.add_argument(
        "-k", type=int, default=None,
        help="jumlah chunks yang dikirim ke model (bawaan: config.N_FINAL)",
    )
    args = parser.parse_args(argv)
    query_text = merge_questions(args.question)

    print(f"Pertanyaan: {query_text}\n")
    content, _, report = answer(query_text, k=args.k)
    print("\nJAWABAN:")
    print(content)
    print(f"\n(cakupan sitasi {report.coverage:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
