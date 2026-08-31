"""Use-case memasukkan dokumen ke antrean ingest — jalur TULIS.

Berbeda dari AnswerService/AgentService yang membaca: ini menerima unggahan,
menyimpan blob-nya, dan menaruh satu tugas di antrean. Ekstraksi sesungguhnya
berjalan asinkron di worker - use-case ini selesai dalam sepersekian detik.

DUA PROPERTI KEAMANAN DIENKAPSULASI DI SINI, DAN KEDUANYA PERNAH SALAH:

  1. UNIT SELALU DARI PENGUNGGAH, tidak pernah dari argumen yang bisa diisi
     pemanggil. Kalau unit menjadi parameter bebas, siapa pun bisa menandai
     dokumennya milik unit lain, dan seluruh pembatas Hari 2 kembali
     bergantung pada kejujuran pengisi formulir. submit() mengambilnya dari
     `uploader.unit` - titik.

  2. KLASIFIKASI GAGAL-TERTUTUP ke `terbatas`. Nilai yang tidak dikenal jatuh
     ke `terbatas`, bukan `umum`. Dokumen yang salah ditandai terbatas hanya
     merepotkan satu orang yang memintanya dibuka; yang salah ditandai umum
     sudah terlanjur terbaca semua orang.

Batas injeksi sama dengan service lain (Opsi A): dependency berat/bertukar -
penyimpanan blob dan antrean - disuntik lewat port; konstanta dibaca langsung.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# Nilai klasifikasi yang sah. Apa pun di luar ini jatuh ke yang paling ketat.
_VALID_CLASSIFICATION = ("terbatas", "umum")
_FAIL_CLOSED = "terbatas"

# Jenis berkas yang diterima - allowlist EKSTENSI di lapis SERVER. file_uploader
# di UI menyaring di sisi klien, tetapi API /documents dan CLI TIDAK lewat
# widget itu. Batas yang hanya dipasang di UI bukan batas - alasan yang sama
# dengan check_size di blob. Allowlist (bukan denylist): yang tak dikenal
# ditolak, bukan dicoba.
_ALLOWED_EXT = (".pdf", ".md", ".txt")


class UnsupportedType(ValueError):
    """Jenis berkas di luar allowlist. Ditolak SEBELUM disimpan/diantrekan."""


class BlobStore(Protocol):
    """Port penyimpanan berkas. Yang sungguhan menulis ke filesystem dan
    memvalidasi ukuran; fake untuk tes cukup menyimpan di memori."""

    def save(self, name: str, content: bytes) -> tuple[str, Path]:
        ...


class TaskQueue(Protocol):
    """Port antrean tugas. Yang sungguhan menulis ke Postgres."""

    def send(self, file_name: str, file_path: str, kind: str, *,
             unit: str | None, classification: str,
             pengunggah: str | None) -> int:
        ...


@dataclass(frozen=True)
class IngestReceipt:
    """Tanda terima unggahan, sebagai DATA."""

    task_id: int
    name: str
    unit: str | None
    classification: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "unit": self.unit,
            "classification": self.classification,
        }


@dataclass
class IngestService:
    """Menerima unggahan, menyimpan blob, menaruh tugas di antrean."""

    blob_store: BlobStore
    task_queue: TaskQueue

    def submit(self, filename: str, content: bytes, *, uploader: Any,
               kind: str = "sop",
               classification: str = _FAIL_CLOSED) -> IngestReceipt:
        """Masukkan satu dokumen ke antrean.

        `uploader` adalah User yang login. Unit dokumen DIAMBIL DARINYA -
        tidak ada parameter unit, dan itu disengaja: unit yang bisa diisi
        pemanggil adalah lubang, bukan fitur.
        """
        # Tamu (PUBLIC) TIDAK boleh mengunggah. Ia identitas baca-saja tanpa
        # unit; membiarkannya menaruh tugas berarti dokumen yatim (unit=None,
        # hanya pemilik yang lihat) menumpuk di antrean atas nama anonim. HTTP
        # API sudah menolaknya lebih dulu; penolakan di sini adalah lapis kedua
        # untuk pemanggil mana pun yang kelak lupa memeriksa - termasuk UI.
        from ragcore.domain.users import PUBLIC
        if uploader is PUBLIC:
            raise PermissionError(
                "Tamu tidak dapat mengunggah dokumen. Masuk lebih dulu.")

        # Jenis berkas dibatasi DI SINI (server), bukan hanya di widget UI.
        # Ekstensi diperiksa dari nama berkas pengunggah; ditolak sebelum blob
        # disimpan atau tugas diantrekan.
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_EXT:
            raise UnsupportedType(
                f"Jenis berkas '{ext or 'tanpa ekstensi'}' tidak diizinkan. "
                f"Hanya {', '.join(_ALLOWED_EXT)} yang diterima.")

        # Klasifikasi gagal-tertutup: apa pun yang bukan nilai sah -> terbatas.
        if classification not in _VALID_CLASSIFICATION:
            classification = _FAIL_CLOSED

        # Unit HANYA dari identitas pengunggah. Tidak ada uploader -> tidak ada
        # unit -> dokumen hanya terlihat pemilik tabel (maksimal tertutup).
        unit = getattr(uploader, "unit", None)
        # NIP pengunggah dititipkan ke antrean supaya UI bisa menampilkan
        # status HANYA ke orang yang mengunggah. Bukan batas keamanan (antrean
        # infrastruktur, bukan data RLS) - murni "tunjukkan dokumen SAYA".
        pengunggah = getattr(uploader, "nip", None)

        name, file_path = self.blob_store.save(filename, content)
        task_id = self.task_queue.send(
            name, str(file_path), kind, unit=unit, classification=classification,
            pengunggah=pengunggah)
        return IngestReceipt(task_id=task_id, name=name, unit=unit,
                             classification=classification)
