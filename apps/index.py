"""Membangun indeks (langkah 3-4: embedding dan storage).

    python apps/index.py            bangun indeks
    python apps/index.py --ulang    hapus indeks lama lebih dulu

Isinya ada di ragcore/indexing/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.index import main

if __name__ == "__main__":
    sys.exit(main())
