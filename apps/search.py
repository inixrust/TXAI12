"""Pencarian: vektor, hybrid, dan penyusunan ulang — ditampilkan berdampingan.

    python apps/search.py "pertanyaan Anda"
    python apps/search.py --semua "pertanyaan Anda"    tanpa filters status

Isinya ada di ragcore/retrieval/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.search import main

if __name__ == "__main__":
    sys.exit(main())
