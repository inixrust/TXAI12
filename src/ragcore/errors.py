"""Kelas errors lab.

Kenapa tidak cukup melempar `RuntimeError` biasa: pemanggil perlu MEMBEDAKAN
"berkasnya belum ada" (peserta tinggal menjalankan satu perintah) dari
"Ollama mati" (masalah lain). app.py memakai pembedaan itu untuk menampilkan
pesan yang bisa ditindaklanjuti, bukan sekadar tumpukan traceback.

Setiap errors mewarisi juga jenis bawaan Python yang paling dekat
(`FileNotFoundError`, `RuntimeError`) supaya kode lama yang menangkap jenis
bawaan tetap bekerja.
"""
from __future__ import annotations


class LabError(Exception):
    """Induk semua errors yang sengaja dilempar kode lab."""


class FileMissing(LabError, FileNotFoundError):
    """Ada berkas yang harus dibuat lebih dulu oleh perintah lain."""


class IndexNotBuilt(FileMissing):
    """Indeks vektor atau chunks BM25 belum ada.

    Jalankan `python -m ragcore.commands.index` dari AKAR lab.
    """


class DocumentFolderMissing(FileMissing):
    """Folder documents/ tidak ditemukan — biasanya karena salah folder kerja."""


class TestsetMissing(FileMissing):
    """testset.json tidak ditemukan; evaluasi tidak bisa dijalankan."""


class EmptyCorpus(LabError, RuntimeError):
    """Folder dokumen ada, tetapi tidak satu pun berkas terbaca."""


class UnreadableDocument(LabError, ValueError):
    """PDF nyaris tanpa lapisan teks — hampir selalu hasil pindaian (modul F4)."""

    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(
            f"{file_name}: nyaris tanpa teks. "
            f"Kemungkinan PDF hasil pindaian, perlu OCR."
        )


class UnsafeExpression(LabError, ValueError):
    """Ekspresi di luar aritmetika sederhana ditolak kalkulator agent (modul A4)."""


class SqlclMissing(LabError, FileNotFoundError):
    """SQLcl tidak ditemukan, jadi server MCP Oracle tidak bisa dijalankan.

    Tanpa pemeriksaan ini kegagalannya muncul jauh di dalam asyncio sebagai
    'WinError 2: The system cannot find the file specified' - tanpa menyebut
    berkas apa yang dicari, apalagi cara memperbaikinya.
    """

    def __init__(self, command: str) -> None:
        super().__init__(
            f"SQLcl tidak ditemukan: '{command}' tidak ada di PATH.\n"
            f"  Server MCP Oracle (L7, L8) butuh SQLcl 26.x + Java 17.\n"
            f"  Perbaiki dengan salah satu cara:\n"
            f"    1. Pasang SQLcl, lalu pastikan '{command}' bisa dipanggil "
            f"dari terminal\n"
            f"    2. Setel SQLCL_HOME ke folder SQLcl (lab menyusun "
            f"perintah java sendiri)\n"
            f"    3. Setel MCP_COMMAND bila perintahnya tidak standar\n"
            f"  Pelajaran yang TIDAK butuh ini tetap jalan: L1-L6, L10-L14."
        )
