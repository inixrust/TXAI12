"""python search.py "pertanyaan" — bandingkan tiga cara mencari.

    python search.py "pertanyaan Anda"           bawaan: hanya dokumen berlaku
    python search.py --semua "pertanyaan Anda"   tanpa filters status (B3)

Ketiga blok hasil ditampilkan berurutan supaya perbedaannya terlihat langsung:
vektor saja, hybrid, lalu hybrid dengan penyusunan ulang.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from .. import config, display
from ..retrieval import expand, retrieve_best, search_hybrid, search_vector
from ._args import add_question_arg, merge_questions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="search.py", description=__doc__)
    add_question_arg(parser)
    parser.add_argument(
        "--semua", dest="everything", action="store_true",
        help="matikan filters status — dokumen yang sudah dicabut ikut muncul",
    )
    args = parser.parse_args(argv)
    query_text = merge_questions(args.question)

    # filters={} berarti tanpa filters; None berarti filters bawaan.
    filters = {} if args.everything else None

    print(f"Pertanyaan: {query_text}")
    if expand(query_text) != query_text:
        print(f"Setelah perluasan singkatan: {expand(query_text)}")
    if args.everything:
        print("Penyaring status DIMATIKAN — dokumen dicabut boleh muncul.")

    display.print_chunks(
        search_vector(query_text, k=config.N_FINAL, filters=filters), "VEKTOR SAJA"
    )
    display.print_chunks(
        search_hybrid(query_text, filters=filters)[: config.N_FINAL], "HYBRID"
    )
    display.print_chunks(
        retrieve_best(query_text, filters=filters), "HYBRID + SUSUN ULANG"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
