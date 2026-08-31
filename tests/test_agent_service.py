"""AgentService: pola use-case + DI dibuktikan di JALUR TERSULIT.

Jalur agent hibrida biasanya butuh SQLcl, Oracle, sesi MCP, dan runtime
LangGraph. Seluruh berkas ini berjalan TANPA satu pun dari itu - karena
ketiganya (sumber tool, model, pabrik agent) disuntik. Kalau suatu saat
AgentService mulai membangun sesi MCP atau memanggil create_agent sungguhan
sendiri, tes ini gagal karena butuh layanan yang tidak ada di sini.

Sekaligus mengunci perbaikan nyata: identitas ContextVar HARUS di-reset
setelah tiap ask(), tidak menetap ke pemanggil berikutnya.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from ragcore.agent.tools_hybrid import ACTIVE_USER
from ragcore.application import AgentOutcome, AgentService


class _Msg:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeAgent:
    """Meniru agent LangGraph: ainvoke() mengembalikan {'messages': [...]}."""

    def __init__(self, answer, tool_name="search_rules"):
        self._answer = answer
        self._tool_name = tool_name
        self.identity_saat_jalan = "BELUM"

    async def ainvoke(self, payload, config=None):
        # tangkap identitas yang aktif SAAT agent jalan - untuk membuktikan
        # ContextVar benar-benar terpasang selama eksekusi
        self.identity_saat_jalan = ACTIVE_USER.get()
        user = _Msg("", tool_calls=[{"name": self._tool_name}])
        final = _Msg(self._answer)
        return {"messages": [user, final]}


class FakeToolSource:
    def __init__(self, tools):
        self._tools = tools
        self.dibuka = 0

    @asynccontextmanager
    async def session(self):
        self.dibuka += 1
        yield self._tools


def _service(answer="Uang harian Rp450.000 [dokumen: SE-12, hal. 1].",
             tools=()):
    captured = {}

    def fake_factory(*, model, tools, system_prompt):
        captured["tools"] = tools
        captured["prompt"] = system_prompt
        return FakeAgent(answer)

    svc = AgentService(llm=object(), tool_source=FakeToolSource(list(tools)),
                       agent_factory=fake_factory)
    return svc, captured


def test_ask_once_tanpa_mcp_atau_langchain():
    svc, captured = _service()
    out = asyncio.run(svc.ask_once("Berapa uang harian?", identity=None))

    assert isinstance(out, AgentOutcome)
    assert "450.000" in out.answer
    assert "search_rules" in out.tools_called
    # search_rules selalu ikut disuntik ke agent, di depan tool basis data
    assert captured["tools"][0].name == "search_rules"


def test_identitas_terpasang_saat_jalan_lalu_direset():
    """ContextVar aktif selama ask(), dan DIKEMBALIKAN setelahnya - inilah
    kebocoran yang diperbaiki: sebelumnya set() tak pernah di-reset."""
    fake_agent_box = {}

    def fake_factory(*, model, tools, system_prompt):
        a = FakeAgent("jawab [dokumen: X, hal. 1].")
        fake_agent_box["agent"] = a
        return a

    svc = AgentService(llm=object(), tool_source=FakeToolSource([]),
                       agent_factory=fake_factory)

    token_awal = ACTIVE_USER.set("SEBELUM")
    try:
        asyncio.run(svc.ask_once("q", identity="orang-A"))
        assert fake_agent_box["agent"].identity_saat_jalan == "orang-A"
        # setelah ask(), context kembali ke nilai pemanggil - tidak bocor
        assert ACTIVE_USER.get() == "SEBELUM"
    finally:
        ACTIVE_USER.reset(token_awal)


def test_session_dipakai_ulang_untuk_banyak_pertanyaan():
    """Satu sesi MCP, banyak pertanyaan dengan identitas berbeda - pola yang
    dipakai harness evaluasi supaya tidak membuka 30 sesi."""
    src = FakeToolSource([])

    def fake_factory(*, model, tools, system_prompt):
        return FakeAgent("jawab [dokumen: X, hal. 1].")

    svc = AgentService(llm=object(), tool_source=src, agent_factory=fake_factory)

    async def jalan():
        async with svc.session() as runner:
            await runner.ask("q1", identity="A")
            await runner.ask("q2", identity="B")

    asyncio.run(jalan())
    assert src.dibuka == 1        # sesi dibuka SEKALI untuk dua pertanyaan


def test_identity_context_hanya_untuk_user_ber_unit():
    """Konteks unit disisipkan HANYA untuk User ber-unit (dari identitas login,
    bukan pertanyaan). Operator/PUBLIC/None tak punya unit -> tanpa konteks."""
    from ragcore.application.agent_service import _identity_context
    from ragcore.domain.users import PUBLIC, REGISTRY

    ctx = _identity_context(REGISTRY["NCS-0031"])   # Sinta, Divisi TI
    assert ctx is not None and "Divisi TI" in ctx
    assert "bukan izin" in ctx                       # tegas: DB tetap penegak
    assert _identity_context(None) is None           # operator
    assert _identity_context(PUBLIC) is None          # anonim, tanpa unit


def test_to_payload_json_serializable():
    import json

    svc, _ = _service()
    out = asyncio.run(svc.ask_once("q", identity=None))
    teks = json.dumps(out.to_payload())
    kembali = json.loads(teks)

    assert "answer" in kembali
    assert "search_rules" in kembali["tools_called"]
    # steps (pesan langchain) TIDAK ikut ke payload
    assert "steps" not in kembali
