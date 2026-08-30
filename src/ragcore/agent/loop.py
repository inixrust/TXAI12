"""Lingkaran agent: panggil model, jalankan alat yang dimintanya, ulangi."""
from __future__ import annotations

from ragcore.domain import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .. import config
from ..model import get_llm
from .tools import TOOL, TOOL_MAP, search_policy

SYSTEM = """Anda asisten internal PT Nusantara Cipta Solusi.

Anda memiliki dua alat:
- cari_kebijakan(pertanyaan): mencari fakta di dokumen internal.
- hitung(ekspresi): menghitung aritmetika.

Aturan:
1. Untuk pertanyaan apa pun tentang aturan, besaran, atau ketentuan, SELALU
   panggil cari_kebijakan lebih dulu. Jangan menjawab dari ingatan.
2. Bila jawaban membutuhkan perhitungan (misalnya total beberapa hari),
   ambil angkanya dari cari_kebijakan lalu panggil hitung.
3. Bila cari_kebijakan menyatakan informasi tidak ditemukan, sampaikan itu apa
   adanya. Jangan mengarang.
4. Jawaban akhir singkat, dalam bahasa Indonesia."""

STEP_MAX = 5
RESULT_SNIPPET_WIDTH = 110

LIMIT_MESSAGE = (
    "(Batas langkah tercapai tanpa jawaban akhir. Sederhanakan pertanyaan, "
    "atau naikkan maks_langkah.)"
)


def _supports_agent(llm: object) -> bool:
    """Mode tiruan dan model tanpa tool-calling tidak bisa menjadi agent."""
    return not config.FAKE_MODE and hasattr(llm, "bind_tools")


def _run_tool(name: str, args: dict) -> str:
    tool = TOOL_MAP.get(name)
    if tool is None:
        return f"Alat '{name}' tidak ada."
    return str(tool.invoke(args))


def run_agent(
    question: str,
    step_max: int = STEP_MAX,
    show_step: bool = True,
) -> str:
    """Jalankan lingkaran agent sampai model memberi jawaban akhir.

    Kembalikan teks jawaban akhir. Setiap panggilan alat dicetak agar peserta
    melihat 'jalan pikiran' agent — bagian terpenting dari demo ini.
    """
    llm = get_llm()

    # Daripada gagal, tunjukkan satu panggilan RAG langsung supaya alurnya
    # tetap terlihat — sejalan dengan filosofi mode tiruan di seluruh lab.
    if not _supports_agent(llm):
        print(
            "  [Agent membutuhkan model dengan tool-calling — mode tiruan tidak "
            "mendukungnya.]"
        )
        print("  [Menampilkan satu panggilan cari_kebijakan langsung sebagai gantinya.]\n")
        return search_policy.invoke({"pertanyaan": question})

    llm_beralat = llm.bind_tools(TOOL)
    message: list = [SystemMessage(SYSTEM), HumanMessage(question)]

    for step in range(1, step_max + 1):
        reply: AIMessage = llm_beralat.invoke(message)
        message.append(reply)

        # Tidak ada panggilan alat -> model sudah siap menjawab.
        if not reply.tool_calls:
            return (reply.content or "").strip()

        for call in reply.tool_calls:
            name, args = call["name"], call["args"]
            if show_step:
                print(f"  [langkah {step}] memanggil {name}({args})")

            result = _run_tool(name, args)

            if show_step:
                cuplik = " ".join(result.split())[:RESULT_SNIPPET_WIDTH]
                print(f"             -> {cuplik}")

            message.append(ToolMessage(content=result, tool_call_id=call["id"]))

    return LIMIT_MESSAGE
