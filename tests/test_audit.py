"""Audit security-first: allowlist, denylist, pemangkasan, dan fail-safe.

Tes-tes ini menjaga janji keamanan modul audit - bahwa ia mencatat FAKTA
aktivitas, tidak pernah muatan sensitif. Semuanya berjalan tanpa Langfuse:
penyaringan diuji langsung (_safe_fields), dan fail-safe dibuktikan dengan
tracing dimatikan.
"""
from __future__ import annotations

from ragcore import audit


def test_hanya_field_allowlist_yang_lolos():
    hasil = audit._safe_fields(
        {"unit": "Divisi TI", "berkas": "a.pdf", "sesuatu_lain": "buang aku"})
    assert hasil == {"unit": "Divisi TI", "berkas": "a.pdf"}


def test_denylist_menang_meski_dipaksa_masuk_allowlist(monkeypatch):
    """Lapis kedua: nama field yang mencurigakan dibuang WALAU seseorang
    keliru menambahkannya ke allowlist. Dua lapis, karena yang satu pasti
    suatu saat khilaf."""
    monkeypatch.setattr(audit, "ALLOWED",
                        audit.ALLOWED | {"password", "isi_dokumen"})
    hasil = audit._safe_fields(
        {"password": "lab2026", "isi_dokumen": "rahasia perusahaan",
         "unit": "Divisi TI"})
    assert hasil == {"unit": "Divisi TI"}, f"rahasia lolos: {hasil}"


def test_nilai_panjang_dipangkas():
    hasil = audit._safe_fields({"alasan": "x" * 500})
    assert len(hasil["alasan"]) <= audit._MAX + 1
    assert hasil["alasan"].endswith("…")


def test_none_dibuang():
    assert audit._safe_fields({"unit": None, "berkas": None}) == {}


def test_record_tak_pernah_menyimpan_sandi(monkeypatch):
    """Bahkan bila pemanggil KHILAF mengoper field bernama sandi, ia tak
    pernah lolos - baik karena di luar allowlist, maupun denylist."""
    hasil = audit._safe_fields(
        {"sandi": "lab2026", "kata_sandi": "x", "token": "abc",
         "unit": "Divisi SDM"})
    assert hasil == {"unit": "Divisi SDM"}


def test_record_fail_safe_saat_tracing_mati(monkeypatch):
    """Server jejak mati / tracing off TIDAK boleh menggagalkan aksi user."""
    monkeypatch.setattr(audit.config, "USE_TRACING", False)
    # Tidak boleh melempar apa pun, walau dioper field aneh.
    audit.record("login-gagal", subject="NCS-0001", outcome="ditolak",
                 sandi="jangan-dicatat")


def test_record_fail_safe_saat_klien_meledak(monkeypatch):
    """Bila tracing menyala tapi klien Langfuse melempar, aksi tetap jalan."""
    monkeypatch.setattr(audit.config, "USE_TRACING", True)
    monkeypatch.setattr(audit, "callback_handler", lambda: None)

    def meledak():
        raise RuntimeError("langfuse mati")

    import langfuse
    monkeypatch.setattr(langfuse, "get_client", meledak)
    audit.record("login", subject="NCS-0001")   # tidak boleh melempar
