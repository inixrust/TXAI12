"""Menyusun jawaban ber-citation dari dokumen internal.

    python apps/answer.py "pertanyaan Anda"

Isinya ada di ragcore/generation/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.answer import main

if __name__ == "__main__":
    sys.exit(main())
