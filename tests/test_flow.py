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


def test_requester_fail_closed_nip_asing():
    """NIP kosong = operator (None/pemilik); NIP TERISI tapi tak dikenal ->
    PUBLIC (umum saja), BUKAN None yang membuka akses pemilik kebal-RLS."""
    from ragcore.domain.users import PUBLIC, REGISTRY
    from ragcore.flow.production import _requester

    nip = next(iter(REGISTRY))
    assert _requester({"nip": nip}) is REGISTRY[nip]
    assert _requester({"nip": ""}) is None
    assert _requester({}) is None
    assert _requester({"nip": "NCS-XXXX-asing"}) is PUBLIC


# --------------------------------- SIAPA yang boleh meninjau (pemisahan tugas)

def test_peninjau_hanya_sdm_pimpinan_dan_direksi():
    """Vonis kepatuhan hanya boleh disetujui pemilik kebijakan: pimpinan Divisi
    SDM (pemilik SOP kepegawaian) atau Direksi. Bukan staf, bukan IT."""
    from ragcore.domain.users import REGISTRY, is_reviewer

    assert is_reviewer(REGISTRY["NCS-0007"])   # Bramantyo - Kepala Divisi SDM
    assert is_reviewer(REGISTRY["NCS-0001"])   # Chandra - Direksi
    # BUKAN peninjau:
    assert not is_reviewer(REGISTRY["NCS-0012"])  # Andini - SDM tapi STAF
    assert not is_reviewer(REGISTRY["NCS-0031"])  # Sinta - pimpinan tapi TI (IT)
    assert not is_reviewer(REGISTRY["NCS-0068"])  # Fitri - Pengadaan, staf


def test_publik_dan_none_bukan_peninjau():
    """Fail-closed: anonim / tanpa identitas / dict lama bukan peninjau."""
    from ragcore.domain.users import PUBLIC, is_reviewer

    assert not is_reviewer(PUBLIC)
    assert not is_reviewer(None)
    assert not is_reviewer({"peran": "pimpinan", "unit": "Divisi SDM"})


def test_authorize_gerbang_keputusan():
    """Gerbang OTORITATIF review_service.authorize (fungsi murni, tanpa DB):
    boleh HANYA bila peninjau berwenang DAN bukan si pemohon."""
    from ragcore.application.review_service import authorize
    from ragcore.domain.users import PUBLIC, REGISTRY

    bram = REGISTRY["NCS-0007"]   # Kepala Divisi SDM - peninjau
    fitri = REGISTRY["NCS-0068"]  # Pengadaan, staf - pemohon
    sinta = REGISTRY["NCS-0031"]  # TI pimpinan - BUKAN peninjau

    assert authorize(bram, fitri.nip) is None          # boleh
    # pemohon sendiri (Bram meninjau permintaan Bram) -> ditolak
    assert "sendiri" in authorize(bram, bram.nip)
    # bukan peninjau (staf) -> ditolak
    assert "berwenang" in authorize(fitri, "NCS-0001")
    # pimpinan TI bukan peninjau kebijakan -> ditolak
    assert "berwenang" in authorize(sinta, fitri.nip)
    # anonim -> ditolak
    assert authorize(PUBLIC, fitri.nip) is not None
