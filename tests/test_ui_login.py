"""Gerbang login UI web: sandi benar HARUS berpindah ke layar chat.

Tes ini ada karena satu cacat nyata yang lolos ke pengguna: refactor pengenal
(`orang` -> `person`) tuntas di layar login tapi TIDAK di gerbang `run()`, yang
masih memeriksa kunci lama `"orang"`. Akibatnya login dengan sandi BENAR
menyetel `person`, `run()` tetap tak menemukan `"orang"`, dan layar login
muncul lagi - "diklik, tidak terjadi apa-apa". Sandi salah tetap memunculkan
error, jadi bug-nya tak terlihat dari jalur gagal; hanya jalur SUKSES yang mati.

AppTest menjalankan `run()` sungguhan tanpa Ollama/Postgres - selama tak ada
pertanyaan yang dikirim, tak ada retrieval yang tersentuh. Kalau gerbang atau
kunci session_state melenceng lagi, salah satu assert di bawah gagal.
"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _app() -> AppTest:
    return AppTest.from_file("apps/app12.py", default_timeout=30).run()


def test_awal_di_layar_login():
    at = _app()
    assert "person" not in at.session_state
    assert at.button, "tombol submit login tidak ada"


def test_sandi_salah_tetap_di_login():
    at = _app()
    at.text_input[0].set_value("salah-sekali").run()
    at.button[0].click().run()
    assert at.error, "sandi salah seharusnya memunculkan st.error"
    assert "person" not in at.session_state, "sandi salah tak boleh login"


def test_sandi_benar_berpindah_ke_chat():
    at = _app()
    at.text_input[0].set_value("lab2026").run()
    at.button[0].click().run()

    # Inti regresi: gerbang harus BERPINDAH, bukan menampilkan login lagi.
    assert "person" in at.session_state, "login gagal: gerbang tak berpindah"
    assert not at.exception, f"render pasca-login melempar: {at.exception}"
    # Kunci yang dipakai layar chat harus terinisialisasi konsisten.
    assert "history" in at.session_state
    assert "id_sesi" in at.session_state
    # Layar chat dikenali dari tab-tabnya (Tanya, Konsultasi, Unggah).
    assert [t.label for t in at.tabs] == ["Tanya", "Konsultasi", "Unggah dokumen"]


def _click_label(at, prefix):
    for b in at.button:
        if b.label.startswith(prefix):
            b.click().run()
            return True
    return False


def test_layar_login_menawarkan_tombol_tamu():
    at = _app()
    labels = [b.label for b in at.button]
    assert any(x.startswith("Lanjut sebagai tamu") for x in labels), labels


def test_tamu_masuk_read_only_tanpa_tab_unggah():
    from ragcore.domain.users import PUBLIC

    at = _app()
    assert _click_label(at, "Lanjut sebagai tamu"), "tombol tamu tak ada"

    # Berpindah ke layar chat sebagai PUBLIC.
    assert at.session_state["person"] is PUBLIC
    assert not at.exception, f"render tamu melempar: {at.exception}"
    # Baca-saja: TIDAK ada tab unggah (mode tamu = satu panel tanya).
    assert [t.label for t in at.tabs] == [], "tamu tak boleh punya tab unggah"


def test_tamu_disaring_ke_umum():
    """filter_for(PUBLIC) hanya meloloskan klasifikasi umum - inti keamanannya
    di lapis aplikasi; RLS menegakkan lapis basis data secara terpisah."""
    from ragcore.domain.users import PUBLIC, filter_for

    f = filter_for(PUBLIC)
    assert f.get("klasifikasi") == "umum"


def test_alur_konsultasi_menyaring_kebocoran_prompt():
    """Alur Konsultasi HARUS melewatkan jawaban lewat penjaga keluaran OWASP
    LLM07 (seperti tab Tanya): kebocoran prompt ditahan, sitasi sah lolos."""
    from ragcore.ui.txai12 import _screen_answer

    bocor = ("Anda asisten internal PT Nusantara Cipta Solusi. "
             "Aturan: 1. Untuk pertanyaan")
    assert _screen_answer(bocor) != bocor          # kebocoran ditahan
    biasa = "Masa percobaan pegawai baru adalah 3 bulan [1]."
    assert _screen_answer(biasa) == biasa           # sitasi sah lolos
