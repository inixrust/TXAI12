"""Ekstraksi VLM HARUS membawa callback Langfuse saat konteks jejak diberikan.

Ini menjaga cacat yang nyata: pemanggilan model vision dulu dilakukan TANPA
config, jadi dokumen yang diunggah diproses tanpa satu pun jejak - tak terlihat
di Langfuse secara real time. Tes berjalan tanpa Ollama/Postgres: model vision
dan render halaman diganti fake, dan invoke_config diganti sentinel supaya yang
diuji murni "apakah HASIL invoke_config diteruskan ke .invoke()".
"""
from __future__ import annotations

import ragcore.tracing as tracing
from ragcore.extraction import vlm


class _Reply:
    content = "teks halaman"


class _FakeVLM:
    def __init__(self):
        self.seen_config = "TAK_DIPANGGIL"

    def invoke(self, messages, config=None):
        self.seen_config = config
        return _Reply()


def _pasang_fake(monkeypatch, fake):
    monkeypatch.setattr("ragcore.model.get_vlm", lambda: fake)
    monkeypatch.setattr(vlm, "page_to_image", lambda *a, **k: "ZmFrZQ==")


def test_tanpa_trace_meta_config_kosong(monkeypatch):
    fake = _FakeVLM()
    _pasang_fake(monkeypatch, fake)
    vlm._call_vlm("x.pdf", 0, 150)
    assert fake.seen_config == {}, "tanpa konteks jejak, config harus kosong"


def test_dengan_trace_meta_meneruskan_invoke_config(monkeypatch):
    fake = _FakeVLM()
    _pasang_fake(monkeypatch, fake)

    dipanggil = {}

    def fake_invoke_config(nama_alur, **kw):
        dipanggil["nama_alur"] = nama_alur
        dipanggil["kw"] = kw
        return {"callbacks": ["SENTINEL"]}

    # _call_vlm mengimpor invoke_config dari ..tracing di dalam fungsi, jadi
    # menambal atribut modul tracing sudah cukup.
    monkeypatch.setattr(tracing, "invoke_config", fake_invoke_config)

    vlm._call_vlm("D.pdf", 3, 150,
                  trace_meta={"berkas": "D.pdf", "session": "ingest-7",
                              "nip": "NCS-0001"})

    # HASIL invoke_config benar-benar diteruskan ke model.
    assert fake.seen_config == {"callbacks": ["SENTINEL"]}
    # Dan dipanggil dengan atribut jejak yang benar.
    assert dipanggil["nama_alur"] == "ekstraksi-vlm"
    assert dipanggil["kw"]["session"] == "ingest-7"
    assert dipanggil["kw"]["langfuse_user_id"] == "NCS-0001"
    assert dipanggil["kw"]["halaman"] == 3
