"""Evaluasi: mengubah 'rasanya lebih baik' menjadi angka yang bisa dibandingkan.

    python apps/evaluate.py              evaluasi retrieval + penyaringan status
    python apps/evaluate.py --penolakan  ikut menguji kemampuan menolak (butuh model)

Isinya ada di ragcore/evaluasi/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.evaluate import main

if __name__ == "__main__":
    sys.exit(main())
