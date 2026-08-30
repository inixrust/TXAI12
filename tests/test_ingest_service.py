"""IngestService: jalur tulis, dengan dua properti keamanan yang diuji ketat.

Nol filesystem, nol Postgres - blob store dan antrean DISUNTIK sebagai fake.
Dua tes di sini adalah yang terpenting di seluruh berkas: mereka membuktikan
unit TIDAK BISA dipalsukan pemanggil, dan klasifikasi GAGAL-TERTUTUP. Keduanya
pernah salah di sistem nyata dan berakibat dokumen terbatas terbaca semua orang.
"""
from __future__ import annotations

from pathlib import Path

from ragcore.application import IngestReceipt, IngestService


class FakeBlobStore:
    def __init__(self):
        self.saved = []

    def save(self, name, content):
        self.saved.append((name, content))
        return name, Path("/blob") / name


class FakeQueue:
    def __init__(self):
        self.sent = None
        self._id = 0

    def send(self, file_name, file_path, kind, *, unit, classification,
             pengunggah=None):
        self._id += 1
        self.sent = {"file_name": file_name, "kind": kind,
                     "unit": unit, "classification": classification,
                     "pengunggah": pengunggah}
        return self._id


class _User:
    def __init__(self, unit, nip="NCS-9999"):
        self.unit = unit
        self.nip = nip


def _service():
    return IngestService(blob_store=FakeBlobStore(), task_queue=FakeQueue())


def test_submit_mengembalikan_receipt():
    svc = _service()
    r = svc.submit("SOP-baru.pdf", b"data", uploader=_User("Divisi TI"))
    assert isinstance(r, IngestReceipt)
    assert r.name == "SOP-baru.pdf"
    assert r.task_id == 1


def test_unit_selalu_dari_pengunggah_tak_bisa_dipalsukan():
    """Kalaupun pemanggil MENCOBA menyisipkan unit lewat kwarg, ia diabaikan -
    unit hanya dari uploader.unit. Ini yang mencegah 'tandai dokumenku milik
    unit lain'."""
    svc = _service()
    # 'unit' bukan parameter submit(); mengirimnya harus error, bukan diam-diam
    # dipakai. Kita buktikan lewat introspeksi + perilaku.
    import inspect
    params = inspect.signature(svc.submit).parameters
    assert "unit" not in params, "submit() tidak boleh punya parameter unit"

    r = svc.submit("x.pdf", b"d", uploader=_User("Divisi SDM"))
    assert r.unit == "Divisi SDM"        # dari uploader, bukan dari mana pun lain


def test_klasifikasi_gagal_tertutup():
    """Nilai tak dikenal -> terbatas, BUKAN umum."""
    svc = _service()
    for jahat in ("umumm", "public", "", "UMUM", "rahasia", "administrator"):
        r = svc.submit("x.pdf", b"d", uploader=_User("Divisi TI"),
                       classification=jahat)
        assert r.classification == "terbatas", (
            f"klasifikasi '{jahat}' seharusnya jatuh ke terbatas, "
            f"bukan {r.classification}")


def test_klasifikasi_umum_eksplisit_dihormati():
    """'umum' yang memang disebut eksplisit tetap boleh."""
    svc = _service()
    r = svc.submit("x.pdf", b"d", uploader=_User("Divisi TI"),
                   classification="umum")
    assert r.classification == "umum"


def test_tanpa_pengunggah_unit_none_maksimal_tertutup():
    """Tidak ada uploader -> unit None + terbatas -> hanya pemilik tabel yang
    melihatnya (maksimal fail-closed)."""
    svc = _service()
    r = svc.submit("x.pdf", b"d", uploader=None)
    assert r.unit is None
    assert r.classification == "terbatas"


def test_to_payload_json_serializable():
    import json

    svc = _service()
    r = svc.submit("x.pdf", b"d", uploader=_User("Divisi TI"))
    kembali = json.loads(json.dumps(r.to_payload()))
    assert kembali["unit"] == "Divisi TI"
    assert kembali["classification"] == "terbatas"


def test_pengunggah_dititipkan_ke_antrean():
    """NIP pengunggah ikut ke antrean, supaya UI bisa menampilkan status HANYA
    ke orang yang mengunggah - bukan antrean seluruh kantor."""
    svc = _service()
    svc.submit("SOP-baru.pdf", b"data", uploader=_User("Divisi TI", "NCS-0031"))
    assert svc.task_queue.sent["pengunggah"] == "NCS-0031"


def test_tamu_public_ditolak_mengunggah():
    """Tamu (PUBLIC) tak boleh menaruh dokumen di antrean.

    PUBLIC adalah identitas baca-saja tanpa unit. Tanpa penolakan ini, unggahan
    tamu menjadi dokumen yatim (unit=None) atas nama anonim - dan UI hanya
    menyembunyikan tombolnya, bukan menutup jalurnya. Lapis kedua ditegakkan di
    service, jadi pemanggil mana pun yang lupa memeriksa tetap tertahan.
    """
    import pytest

    from ragcore.domain.users import PUBLIC

    svc = _service()
    with pytest.raises(PermissionError):
        svc.submit("SOP-baru.pdf", b"data", uploader=PUBLIC)


def test_adapter_postgres_menerima_pengunggah():
    """Adapter nyata (_PostgresTaskQueue) HARUS sesignatur dengan port TaskQueue.

    Bug nyata: Protocol dan queue.send diperbarui menerima `pengunggah`, tapi
    adapter di wiring.py TIDAK - dan tes yang memakai FakeQueue tak menangkapnya
    karena FakeQueue-nya sendiri sudah diperbarui. Cek tanda tangan langsung,
    tanpa Postgres, menutup celah itu.
    """
    import inspect

    from ragcore.application.wiring import _PostgresTaskQueue

    params = inspect.signature(_PostgresTaskQueue.send).parameters
    assert "pengunggah" in params, "adapter antrean lupa kwarg 'pengunggah'"
