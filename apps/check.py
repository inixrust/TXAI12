"""Pemeriksaan kesiapan. JALANKAN INI PALING PERTAMA.

    python apps/check.py

Isinya ada di ragcore/doctor.py; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.check import main

if __name__ == "__main__":
    sys.exit(main())
