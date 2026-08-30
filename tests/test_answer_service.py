"""AnswerService: use-case murni dengan dependency disuntik.

Seluruh berkas ini berjalan TANPA Ollama, Postgres, maupun env - itulah
buktinya bahwa aturan 7 (semua dependency di-inject dan bisa diganti fake)
benar-benar dipenuhi, bukan sekadar diklaim. Kalau suatu saat AnswerService
mulai mengambil sesuatu dari global lagi, tes ini gagal karena butuh layanan
yang tidak ada di sini.
"""
from __future__ import annotations

import pytest

from ragcore.application import AnswerOutcome, AnswerService
from ragcore.domain import Document


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.seen = None

    def retrieve(self, question, *, k=None, filters=None, person=None):
        self.seen = {"question": question, "k": k, "filters": filters,
                     "person": person}
        return self.chunks


class _Reply:
    def __init__(self, text):
        self.content = text


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def invoke(self, prompt, config=None):
        self.calls += 1
        return _Reply(self.text)


def _chunks():
    return [Document(page_content="Masa percobaan 3 bulan.",
                     metadata={"source": "SOP-01.pdf", "page": 1})]


def test_ask_tanpa_dependency_nyata():
    svc = AnswerService(retriever=FakeRetriever(_chunks()),
                        llm=FakeLLM("Masa percobaan 3 bulan [1]."))
    out = svc.ask("Berapa lama masa percobaan?", app_user=None)

    assert isinstance(out, AnswerOutcome)
    assert "3 bulan" in out.content
    assert len(out.chunks) == 1
    assert out.report.coverage == pytest.approx(1.0)


def test_ask_tidak_mencetak(capsys):
    """Use-case MURNI: peringatan dikembalikan sebagai data, bukan dicetak.
    Sebuah handler API tidak boleh menyemburkan apa pun ke stdout."""
    svc = AnswerService(retriever=FakeRetriever(_chunks()),
                        llm=FakeLLM("Jawaban tanpa sitasi sama sekali."))
    out = svc.ask("apa pun", app_user=None)

    keluaran = capsys.readouterr()
    assert keluaran.out == "", f"use-case mencetak ke stdout: {keluaran.out!r}"
    assert isinstance(out.warnings, list)


def test_identitas_diteruskan_ke_retriever():
    """person (lapis DB) dan filters (lapis aplikasi) sampai ke port."""
    fake = FakeRetriever(_chunks())
    svc = AnswerService(retriever=fake, llm=FakeLLM("x [1]."))
    svc.ask("q", app_user=None, person="orang-db")

    assert fake.seen["person"] == "orang-db"
    assert fake.seen["filters"] is not None   # filter_for(None) tetap memberi status aktif


def test_korpus_kosong_tidak_memanggil_llm():
    """Tanpa potongan, tidak ada yang perlu dijawab - hemat panggilan model."""
    llm = FakeLLM("mestinya tidak dipanggil")
    svc = AnswerService(retriever=FakeRetriever([]), llm=llm)
    out = svc.ask("q", app_user=None)

    assert llm.calls == 0
    assert out.content  # NOT_FOUND, bukan kosong


def test_to_payload_json_serializable():
    """Boundary DTO: hasil use-case harus bisa jadi JSON tanpa membocorkan
    tipe langchain. Ini yang membuat klaim 'siap API' benar-benar berdiri."""
    import json

    svc = AnswerService(retriever=FakeRetriever(_chunks()),
                        llm=FakeLLM("Masa percobaan 3 bulan [1]."))
    out = svc.ask("q", app_user=None)

    payload = out.to_payload()
    teks = json.dumps(payload)          # tidak boleh melempar
    kembali = json.loads(teks)

    assert kembali["content"] == out.content
    assert kembali["sources"][0]["source"] == "SOP-01.pdf"
    assert "coverage" in kembali
    # kontrak transport tidak boleh menumpahkan isi dokumen
    assert "page_content" not in teks
