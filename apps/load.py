"""Memuat dan memotong dokumen (langkah 1-2), lalu tunjukkan satu contoh.

    python apps/load.py

Isinya ada di ragcore/indexing/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.load import main

if __name__ == "__main__":
    sys.exit(main())
