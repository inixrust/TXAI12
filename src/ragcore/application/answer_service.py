"""Use-case menjawab pertanyaan — MURNI, tanpa efek samping, dependency disuntik.

KENAPA LAPISAN INI ADA.

Sebelumnya use-case inti hidup di `generation.answer()`, dan ia mencampur tiga
hal yang seharusnya terpisah:

    orkestrasi   ambil potongan -> susun jawaban -> periksa sitasi
    dependency   get_llm(), retrieve_best() diambil dari GLOBAL
    presentasi   display.print_chunks(...) dan print(peringatan) ke TERMINAL

Akibatnya sebuah handler API yang memanggilnya akan menyemburkan print ke log
server, dan tidak ada tes yang bisa merakit pipeline terisolasi tanpa Ollama
atau Postgres hidup - dependency-nya tidak bisa diganti fake.

`AnswerService` memisahkan use-case dari keduanya:

  - Dependency BERAT yang benar-benar bisa ditukar DISUNTIK: retriever
    (membungkus store + embedding + reranker) dan model bahasa. Mengganti
    pgvector dengan yang lain, atau Ollama dengan penyedia lain, cukup merakit
    service dengan port yang berbeda - domain tidak tersentuh.

  - TIDAK ada print. Peringatan sitasi dikembalikan sebagai DATA di dalam
    hasil; yang memutuskan menampilkannya adalah pemanggil (CLI mencetak,
    tes memeriksa list-nya, API menyerialisasi lewat AnswerOutcome.to_payload()).

BATAS INJEKSI, DISENGAJA (bukan kelalaian).

Yang disuntik hanya dependency berat/bertukar. Konstanta kebijakan -
config.NOT_FOUND, ambang cakupan, prompt template, sink tracing - dibaca
LANGSUNG lewat kolaborator (compose_answer, check_citation, filter_for),
bukan disuntik. Menyuntik setiap konstanta config akan menambah lapisan tanpa
imbalan: nilai-nilai itu tidak ditukar saat runtime maupun saat tes. Kalau
suatu saat salah satunya memang perlu bervariasi (mis. prompt per-tenant),
BARU ia naik menjadi dependency yang disuntik - saat itu, bukan sekarang.

Konsekuensinya jujur: service ini bebas dari Ollama dan Postgres (terbukti di
test_answer_service.py yang jalan tanpa keduanya), tetapi TIDAK bebas dari
config. Itu batas yang dipilih, dan cukup untuk tujuan sebenarnya - use-case
yang bisa diuji deterministik dan storage/model yang bisa ditukar.

CLI, Streamlit, dan API menjadi tiga adapter tipis di atas service yang sama.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ragcore.domain import Document
from ragcore.generation.answerer import compose_answer
from ragcore.generation.citation import (
    CitationReport,
    check_citation,
    citation_warnings,
)
from ragcore.retrieval.filters import filter_for

_UNSET = object()


class Retriever(Protocol):
    """Port pencarian potongan. Apa pun yang memenuhinya bisa disuntik -
    yang sungguhan (hybrid + rerank di pgvector) maupun fake untuk tes."""

    def retrieve(self, question: str, *, k: int | None = None,
                 filters: Any = None, person: Any = None) -> list[Document]:
        ...


@dataclass(frozen=True)
class AnswerOutcome:
    """Hasil use-case sebagai DATA. Peringatan ikut di sini, bukan dicetak."""

    content: str
    chunks: list[Document]
    report: CitationReport
    warnings: list[str]

    def to_payload(self) -> dict[str, Any]:
        """Bentuk yang aman diserialisasi ke JSON - untuk adapter API.

        AnswerOutcome sendiri memuat Document (langchain) dan CitationReport
        yang TIDAK JSON-serializable. Boundary ini yang memisahkan tipe
        internal dari kontrak transport: API mengirim hasil to_payload(),
        bukan objek mentahnya, jadi bentuk balasan API tidak terikat pada
        struktur internal langchain maupun modul generation.

        Sumber sengaja hanya metadata (asal + halaman), bukan isi potongan:
        balasan API tidak perlu - dan tidak seharusnya - menumpahkan seluruh
        teks dokumen internal.
        """
        return {
            "content": self.content,
            "coverage": self.report.coverage,
            "warnings": list(self.warnings),
            "sources": [
                {"source": d.metadata.get("source"),
                 "page": d.metadata.get("page")}
                for d in self.chunks
            ],
        }


@dataclass
class AnswerService:
    """Menjawab satu pertanyaan dari korpus, dengan dua lapis hak akses.

    Dependency yang bisa ditukar disuntik; sisanya fungsi murni.
    """

    retriever: Retriever
    llm: Any                      # apa pun dengan .invoke() — ChatOllama atau FakeLLM

    def ask(self, question: str, *, app_user: Mapping[str, Any] | None = None,
            person: Any = _UNSET, k: int | None = None,
            session: str | None = None) -> AnswerOutcome:
        """Jalankan use-case. Tidak mencetak apa pun.

        DUA LAPIS HAK AKSES, DAN KEDUANYA BISA DISETEL TERPISAH:

          app_user -> lapis APLIKASI. Menentukan apa yang PANTAS ditampilkan.
          person   -> lapis BASIS DATA. Menentukan apa yang BOLEH dibaca (RLS).

        Bawaannya `person` mengikuti `app_user`, karena itu yang benar dalam
        pemakaian biasa. Keduanya dipisah supaya bisa diperagakan di kelas:
        matikan lapis aplikasi sambil MEMPERTAHANKAN identitas basis data,
        lalu tunjukkan hasilnya tetap tersaring RLS.
        """
        if person is _UNSET:
            person = app_user if not isinstance(app_user, Mapping) else None

        chunks = self.retriever.retrieve(
            question, k=k, filters=filter_for(app_user), person=person)

        content = compose_answer(self.llm, question, chunks,
                                 person=person, session=session)
        report = check_citation(content, len(chunks))
        warnings = list(citation_warnings(report, content))
        return AnswerOutcome(content, chunks, report, warnings)
