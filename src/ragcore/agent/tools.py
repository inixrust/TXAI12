"""Alat yang boleh dipanggil agent.

Dua alat sengaja dipilih agar satu pertanyaan bisa membutuhkan KEDUANYA:

    cari_kebijakan  -> mengambil fakta dari dokumen (seluruh pipeline RAG)
    hitung          -> aritmetika sederhana yang aman

Pertanyaan "dinas 3 hari golongan Manajer, berapa totalnya?" memaksa agent
mencari besaran harian dulu (cari_kebijakan), lalu mengalikannya (hitung) —
demo dua langkah yang tidak bisa diselesaikan satu alat saja.

Docstring setiap alat BUKAN hiasan: itulah keterangan yang dibaca model untuk
memutuskan kapan alat dipakai. Menulisnya asal-asalan sama dengan memberi
petunjuk yang kabur kepada rekan kerja baru.
"""
from __future__ import annotations

from langchain_core.tools import tool

from .. import config
from ..generation.answerer import compose_answer
from ..model import get_llm
from ..retrieval.retriever import retrieve_best
from .arithmetic import eval_expression


@tool
def search_policy(question: str) -> str:
    """Cari jawaban dari dokumen internal perusahaan (SOP, surat edaran, notulen).

    Gunakan untuk semua pertanyaan tentang aturan, prosedur, besaran, batas nilai,
    kewenangan, atau ketentuan apa pun. Jangan menebak dari ingatan — selalu
    lewat alat ini. Masukan: pertanyaan dalam bahasa Indonesia. Keluaran: jawaban
    ber-citation dari dokumen, atau pernyataan bahwa informasinya tidak ditemukan.
    """
    chunks = retrieve_best(question)
    if not chunks:
        return config.NOT_FOUND
    # Perhatikan: yang dipakai di sini model TANPA alat. Kalau alat memanggil
    # LLM ber-alat lagi, ia bisa mencoba memanggil alat di dalam alat — rekursi
    # yang membingungkan. `bind_tools` di lingkaran.py menghasilkan objek baru,
    # jadi model dasar ini tetap polos.
    return compose_answer(get_llm(), question, chunks)


@tool
def count(expression: str) -> str:
    """Hitung ekspresi aritmetika, misalnya '500000 * 3' atau '(2 + 3) * 4'.

    Hanya menerima angka dan operator + - * / % ( ). Tidak menjalankan kode lain.
    Gunakan untuk mengalikan, menjumlahkan, atau menghitung total dari angka yang
    Anda peroleh dari cari_kebijakan.
    """
    try:
        return str(eval_expression(expression))
    except Exception:
        # Alat tidak boleh melempar errors ke lingkaran agent: model justru
        # perlu MEMBACA kegagalannya supaya bisa mencoba ekspresi lain.
        return f"Ekspresi tidak bisa dihitung: {expression!r}"


TOOL = [search_policy, count]
TOOL_MAP = {a.name: a for a in TOOL}
