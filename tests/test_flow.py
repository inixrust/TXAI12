"""Aturan keputusan graf L10 sebagai fungsi MURNI - tanpa Ollama/Postgres.

Inti "kasus nyata"-nya ada di sini: KAPAN jawaban ditahan untuk ditinjau
manusia. Aturannya deterministik dan ditulis kita, bukan diputus model - jadi
bisa DAN harus diuji langsung, cepat, tanpa layanan.

  - Pertanyaan FAKTA yang kokoh  -> dijawab langsung (lolos).
  - Pertanyaan PENILAIAN/kepatuhan -> ditahan untuk disetujui manusia.
  - Cakupan sitasi rendah / sumber pindaian belum diverifikasi -> ditahan.
  - Menolak menjawab (NOT_FOUND) -> lolos; tak ada vonis untuk ditinjau.
"""
from __future__ import annotations

from ragcore import config
from ragcore.domain import Document
from ragcore.flow.production import _hold_reason, n_classify, needs_review


def _doc(mutu: str = "lolos") -> Document:
    return Document(page_content="x", metadata={"mutu_ekstraksi": mutu})


def test_deteksi_pertanyaan_penilaian():
    assert n_classify({"question": "Apakah saya boleh cuti 20 hari?"})["judgment"]
    assert n_classify({"question": "Bolehkah mengambil cuti sekaligus?"})["judgment"]
    assert not n_classify(
        {"question": "Berapa lama masa percobaan pegawai baru?"})["judgment"]


def test_penilaian_ditahan_meski_kokoh():
    """Vonis kepatuhan ditahan WALAU cakupan sitasi sempurna - risikonya bukan
    pada grounding, tapi pada konsekuensi keputusannya."""
    assert needs_review({"answer_text": "boleh", "judgment": True,
                         "coverage": 1.0, "chunks": [_doc()]}) == "tinjau"


def test_fakta_kokoh_lolos():
    assert needs_review({"answer_text": "3 bulan", "judgment": False,
                         "coverage": 1.0, "chunks": [_doc()]}) == "lolos"


def test_menolak_menjawab_tak_ditinjau():
    """NOT_FOUND lolos meski pertanyaannya penilaian - tak ada yang dirilis."""
    assert needs_review(
        {"answer_text": config.NOT_FOUND, "judgment": True}) == "lolos"


def test_cakupan_rendah_ditahan():
    assert needs_review({"answer_text": "x", "judgment": False,
                         "coverage": config.COVERAGE_THRESHOLD - 0.01,
                         "chunks": [_doc()]}) == "tinjau"


def test_sumber_pindaian_belum_verifikasi_ditahan():
    assert needs_review({"answer_text": "x", "judgment": False, "coverage": 1.0,
                         "chunks": [_doc("perlu_tinjau")]}) == "tinjau"


def test_hold_reason_menyebut_kepatuhan():
    assert "kepatuhan" in _hold_reason({"judgment": True})
