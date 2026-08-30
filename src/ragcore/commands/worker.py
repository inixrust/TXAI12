"""python -m ragcore.commands.worker — proses queue ingest.

    python -m ragcore.commands.worker            jalan terus
    python -m ragcore.commands.worker --sekali   satu tugas lalu berhenti

BOLEH DIJALANKAN LEBIH DARI SATU. Dua jendela terminal, dua pekerja, dan
keduanya aman: retrieval tugas memakai FOR UPDATE SKIP LOCKED, sehingga
tidak ada dokumen yang diproses dua kali. Itu peragaan yang layak dilakukan
di kelas - jalankan dua pekerja, unggah lima dokumen, lihat keduanya
berbagi beban tanpa saling menunggu.

Ctrl-C aman. Tugas yang sedang dipegang akan diambil kembali oleh pekerja
mana pun setelah batas macet terlewat.
"""
from __future__ import annotations

import sys

from ..ingest import worker


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    worker.run(sekali="--sekali" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
