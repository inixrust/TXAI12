"""Menyatukan retrieval, prompt, dan pemeriksaan sitasi menjadi satu jawaban."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from ragcore.domain import Document

from .. import config, display
from .citation import CitationReport
from .prompt import TEMPLATE, assemble_context


class AnswerResult(NamedTuple):
    """Bisa dibongkar seperti tuple: `isi, potongan, laporan = jawab(...)`."""

    content: str
    chunks: list[Document]
    report: CitationReport


def compose_answer(llm: Any, question: str, chunks: Sequence[Document],
                  person: Any = None, session: str | None = None,
                  **metadata: Any) -> str:
    """Rakit konteks, kirim ke model, kembalikan teks jawabannya.

    Dipisah sebagai fungsi tersendiri karena dipakai ulang oleh pola agentic
    di modul A2 dan A3 — di situ potongannya sudah disaring lebih dulu.

    DI SINILAH JEJAK DIPASANG (TX-AI12 L12), dan tempatnya memang harus di
    sini: ini satu-satunya titik yang dilewati SETIAP jawaban, baik dari
    perintah baris, antarmuka web, maupun graf LangGraph.

    Sempat terlewat saat lab disusun: modul tracing.py lengkap, kuncinya benar,
    check_trace_keys() mengembalikan True — tetapi tidak ada satu pun jejak yang
    sampai, karena llm.invoke() dipanggil TANPA config. Pipanya ada,
    sambungannya tidak. Tidak ada galat di sisi mana pun.
    """
    if not chunks:
        return config.NOT_FOUND

    from ..tracing import invoke_config

    prompt = TEMPLATE.invoke(
        {"konteks": assemble_context(chunks), "pertanyaan": question}
    )
    # PRIVASI: yang dikirim ke server tracing hanya jumlah dan asal chunks,
    # bukan isinya. Lihat catatan di tracing.invoke_config().
    trace_meta = {
        "chunk_count": len(chunks),
        "sumber": sorted({d.metadata.get("source", "?") for d in chunks}),
        "dari_vlm": sum(d.metadata.get("ekstraksi") == "vlm" for d in chunks),
        **metadata,
    }
    return llm.invoke(
        prompt,
        config=invoke_config("jawab-sop", person=person, session=session,
                                  **trace_meta),
    ).content.strip()


_NO_VALUE = object()


def answer(
    question: str,
    app_user: Mapping[str, Any] | None = None,
    k: int | None = None,
    show_chunks: bool = True,
    person: Any = _NO_VALUE,
    session: str | None = None,
) -> AnswerResult:
    """Ambil potongan, susun jawaban, lalu periksa sitasinya.

    DUA LAPIS HAK AKSES, DAN KEDUANYA BISA DISETEL TERPISAH:

      pengguna -> lapis APLIKASI. Menentukan apa yang PANTAS ditampilkan.
      orang    -> lapis BASIS DATA. Menentukan apa yang BOLEH dibaca.

    Bawaannya `orang` mengikuti `pengguna`, karena itu yang benar dalam
    pemakaian biasa. Keduanya dipisah supaya bisa diperagakan di kelas:
    matikan lapis aplikasi (pengguna=None) sambil MEMPERTAHANKAN identitas
    basis data (orang=...), lalu tunjukkan bahwa hasilnya tetap tersaring.

    Kalau keduanya ikut dimatikan, yang teruji bukan RLS melainkan tidak
    ada apa-apa - sambungan kembali memakai pemilik tabel yang kebal.
    """
    # ADAPTER PRESENTASI di atas AnswerService.
    #
    # Use-case-nya sendiri (orkestrasi + hak akses) sekarang murni di
    # application/answer_service.py, dengan dependency disuntik. Fungsi ini
    # tinggal menambahkan yang khas terminal: mencetak potongan lebih dulu,
    # lalu peringatan sitasi. CLI dan Streamlit memanggilnya; API memanggil
    # service-nya langsung dan menyerialisasi lewat AnswerOutcome.to_payload()
    # (Document mentah tidak JSON-serializable — itulah gunanya boundary itu).
    #
    # Impor ditunda: application/ mengimpor compose_answer dari modul ini,
    # jadi impor eager di puncak akan membentuk siklus. Ditunda ke sini,
    # keduanya sudah selesai dimuat saat fungsi ini dipanggil.
    from ragcore.application import build_answer_service

    kwargs: dict[str, Any] = {"app_user": app_user, "k": k, "session": session}
    if person is not _NO_VALUE:
        kwargs["person"] = person

    outcome = build_answer_service().ask(question, **kwargs)

    if show_chunks:
        display.print_chunks(outcome.chunks, snippet_width=84)
    for message in outcome.warnings:
        print(f"  {message}")

    return AnswerResult(outcome.content, outcome.chunks, outcome.report)
