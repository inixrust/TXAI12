"""Use-case agent hibrida (dokumen + basis data) — jalur yang lebih sulit.

Ini pembuktian pola AnswerService di kasus yang jauh lebih menantang: agent
LangGraph di dalam sesi MCP, dengan identitas yang mengalir ke tool lewat
ContextVar. Tiga hal yang jalur ini paksa hadapi, dan yang AnswerService
sederhana tidak:

  1. LIFECYCLE SESI TERPISAH DARI EKSEKUSI. Membuka sesi MCP mahal, jadi
     evaluasi memakai ulang SATU agent untuk puluhan pertanyaan. Karena itu
     `session()` (buka sesi, rakit agent) dipisah dari `AgentRunner.ask()`
     (jalankan satu pertanyaan). CLI yang hanya bertanya sekali memakai
     `ask_once()` yang membungkus keduanya.

  2. IDENTITAS LEWAT ContextVar - DAN DI-RESET. LLM yang memanggil tool
     `search_rules(pertanyaan)` tidak bisa diberi identitas lewat argumen
     (argumen tool diisi model). ContextVar adalah cara yang benar meneruskan
     konteks-permintaan ke tool yang dipanggil framework. Yang SEBELUMNYA
     salah: `ACTIVE_USER.set(person)` dipanggil tanpa pernah di-reset, jadi
     identitas menetap di context setelah agent selesai. Di sini set/reset
     dienkapsulasi per-`ask()` lewat token - tidak bisa lupa, tidak bocor.

  3. DEPENDENCY BERAT DISUNTIK. llm, sumber tool (sesi MCP), dan PABRIK agent
     (`create_agent`) semuanya disuntik. Itu yang membuat use-case ini bisa
     diuji TANPA MCP, Oracle, maupun langchain - lihat test_agent_service.py.

Batas injeksi sama dengan AnswerService (Opsi A): yang berat/bertukar
disuntik; SYSTEM_PROMPT dan konfigurasi tracing dibaca langsung. Harness
evaluasi sengaja TIDAK memakai lapisan ini - ia perlu kendali tingkat-rendah
(timeout, recursion_limit, jawaban tak disaring untuk scoring), dan itu wajar:
alat ukur berada di bawah use-case produk, bukan di atasnya.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

from ragcore.agent.tools_hybrid import ACTIVE_USER, SYSTEM_PROMPT, search_rules
from ragcore.domain.guard import screen
from ragcore.evaluation.hybrid import tools_called
from ragcore.tracing import invoke_config


class ToolSource(Protocol):
    """Port sumber tool basis data. Yang sungguhan membuka sesi MCP; fake
    untuk tes cukup menghasilkan daftar tool tiruan tanpa proses apa pun."""

    def session(self) -> AbstractAsyncContextManager[list]:
        ...


def _default_filter(db_tools: list) -> list:
    from ragcore.agent.hybrid import filter_tools

    return filter_tools(db_tools)


@dataclass(frozen=True)
class AgentOutcome:
    """Hasil satu pertanyaan agent, sebagai DATA. Jawaban akhir SUDAH disaring
    guard keluaran; langkah perantara disimpan untuk diagnosis, bukan dicetak."""

    answer: str
    tools_called: list[str]
    steps: list[Any]

    def to_payload(self) -> dict[str, Any]:
        """Bentuk JSON-serializable untuk adapter API.

        Langkah perantara (steps) SENGAJA tidak ikut: ia objek pesan langchain
        yang tak serializable, dan isinya alat diagnosis internal - bukan yang
        pantas dikirim sebagai balasan.
        """
        return {
            "answer": self.answer,
            "tools_called": list(self.tools_called),
        }


class AgentRunner:
    """Agent hidup di dalam satu sesi MCP. `ask()` boleh dipanggil berkali-kali
    dengan identitas berbeda tanpa membuka sesi baru."""

    def __init__(self, agent: Any):
        self._agent = agent

    async def ask(self, question: str, *, identity: Any = None) -> AgentOutcome:
        # Identitas dipasang ke ContextVar supaya tool search_rules yang
        # dipanggil model tunduk pada dua lapis hak akses yang sama. Token
        # menjamin ia DI-RESET setelah selesai - tidak menetap ke pemanggil
        # berikutnya.
        token = ACTIVE_USER.set(identity)
        try:
            result = await self._agent.ainvoke(
                {"messages": [{"role": "user", "content": question}]},
                config=invoke_config("hibrida", question=question),
            )
            messages = result["messages"]
            called = tools_called(messages)
            # Jawaban AKHIR melewati guard keluaran (LLM07). Giliran perantara
            # tidak disaring: alat diagnosis, bukan yang dilihat pengguna.
            answer = screen(messages[-1].content, called)
            return AgentOutcome(answer=answer,
                                tools_called=sorted(called),
                                steps=list(messages[:-1]))
        finally:
            ACTIVE_USER.reset(token)


@dataclass
class AgentService:
    """Use-case agent hibrida. Dependency berat disuntik; SYSTEM_PROMPT dibaca
    langsung (Opsi A)."""

    llm: Any
    tool_source: ToolSource
    agent_factory: Callable[..., Any]
    system_prompt: str = SYSTEM_PROMPT
    tool_filter: Callable[[list], list] = field(default=_default_filter)

    @asynccontextmanager
    async def session(self, *, tool_all: bool = False):
        """Buka sesi MCP, rakit agent, hasilkan AgentRunner yang bisa dipakai
        ulang untuk banyak pertanyaan."""
        async with self.tool_source.session() as db_tools:
            used = db_tools if tool_all else self.tool_filter(db_tools)
            agent = self.agent_factory(
                model=self.llm,
                tools=[search_rules, *used],
                system_prompt=self.system_prompt,
            )
            yield AgentRunner(agent)

    async def ask_once(self, question: str, *, identity: Any = None,
                       tool_all: bool = False) -> AgentOutcome:
        """Jawab satu pertanyaan: buka sesi, jalankan, tutup. Untuk CLI/API
        yang hanya bertanya sekali."""
        async with self.session(tool_all=tool_all) as runner:
            return await runner.ask(question, identity=identity)
