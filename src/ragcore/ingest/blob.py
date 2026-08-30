"""Penyimpanan berkas masuk — pengganti blob storage untuk lab ini.

Silabus pembanding menyebut "blob storage service" (MinIO, S3). Di lab ini
berkas disimpan di folder, dan itu keputusan sadar: nol container baru pada
mesin yang sudah penuh. Yang PENTING dipelajari peserta bukan MinIO-nya,
melainkan pemisahannya:

    BERKAS ASLI disimpan terpisah dari INDEKS, dan disimpan LEBIH DULU.

Kenapa lebih dulu: begitu users menekan unggah, berkasnya harus sudah
aman meski seluruh pipeline sesudahnya gagal. Ekstraksi bisa diulang;
berkas yang tidak pernah tersimpan tidak bisa.

Kenapa terpisah: indeks adalah TURUNAN. Ia dibangun ulang saat model
embedding berganti, saat pemotong diperbaiki, saat ukuran chunks disetel.
Setiap pembangunan ulang menuntut berkas aslinya masih ada. Sistem yang
membuang berkas setelah mengindeksnya telah mengunci dirinya pada keputusan
yang dibuat hari itu.

Untuk pindah ke MinIO atau S3, yang berubah hanya isi modul ini.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from .. import config

# Folder berkas yang diunggah lewat ui. Terpisah dari `documents/` dan
# `scanned_documents/` yang merupakan korpus bawaan lab.
LOGIN_ROOT: Path = config.ROOT / "incoming_documents"

# Nama berkas yang boleh dipakai di disk. Selain ini digantikan garis bawah.
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_name(name: str) -> str:
    """Nama berkas yang aman ditulis ke disk.

    BUKAN kosmetik. Nama berkas datang dari users, dan nama seperti
    "../../etc/passwd" atau "C:\\Windows\\system32\\x" akan ditulis persis
    sebagaimana diminta bila diteruskan apa adanya. Setiap komponen jalur
    dibuang, lalu sisanya dibersihkan.
    """
    dasar = Path(name.replace("\\", "/")).name or "tanpa-nama"
    bersih = _SAFE.sub("_", dasar).strip("._") or "tanpa-nama"
    return bersih[:120]


class TooLarge(ValueError):
    """Berkas melampaui batas unggah. Ditolak SEBELUM apa pun disimpan."""


def check_size(content: bytes) -> None:
    """Tolak berkas yang melampaui config.MAX_UPLOAD_MB.

    Diperiksa DI SINI, di titik storage, bukan di ui. Antarmuka
    web punya setelan `maxUploadSize` sendiri, tetapi perintah CLI
    `commands.upload` sama sekali tidak melewatinya. Batas yang hanya
    dipasang di satu jalur bukan batas.
    """
    mb = len(content) / (1024 * 1024)
    if mb > config.MAX_UPLOAD_MB:
        raise TooLarge(
            f"berkas {mb:.1f} MB melampaui batas "
            f"{config.MAX_UPLOAD_MB:.0f} MB")


def save(name: str, content: bytes) -> tuple[str, Path]:
    """Simpan berkas masuk. Kembalikan (nama aman, jalur lengkap).

    Tiap unggahan mendapat foldernya sendiri bernama UUID. Dengan begitu dua
    orang yang mengunggah "SOP.pdf" pada menit yang sama tidak saling
    menimpa - dan yang kedua tidak diam-diam menghapus dokumen yang pertama.
    """
    check_size(content)
    safe = safe_name(name)
    folder = LOGIN_ROOT / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / safe
    file_path.write_bytes(content)
    return safe, file_path


def list_files() -> list[Path]:
    """Seluruh berkas yang pernah diunggah."""
    if not LOGIN_ROOT.exists():
        return []
    return sorted(p for p in LOGIN_ROOT.rglob("*") if p.is_file())
