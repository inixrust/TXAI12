"""python agent.py "pertanyaan" — agent yang memilih & memanggil alat sendiri.

    python agent.py "Saya dinas 3 hari golongan Manajer, berapa total uang hariannya?"
    python agent.py "Berapa panjang minimum kata sandi sistem internal?"

Pertanyaan pertama membutuhkan DUA alat: cari besaran hariannya lebih dulu,
lalu kalikan. Perhatikan baris [langkah n] — itulah 'jalan pikiran' agent.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from ..agent import STEP_MAX, run_agent
from ._args import add_question_arg

AGENT_QUESTIONS = "Saya dinas 3 hari golongan Manajer, berapa total uang hariannya?"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent.py", description=__doc__)
    add_question_arg(parser)
    parser.add_argument(
        "--maks-langkah", dest="step_max", type=int, default=STEP_MAX,
        help=f"batas putaran lingkaran agent (bawaan: {STEP_MAX})",
    )
    args = parser.parse_args(argv)
    query_text = " ".join(args.question).strip() or AGENT_QUESTIONS

    print(f"Pertanyaan: {query_text}\n")
    answer_text = run_agent(query_text, step_max=args.step_max)
    print("\nJAWABAN AGEN:")
    print(answer_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
