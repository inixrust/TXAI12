"""Penjaga tool basis data agent: tolak anonim, saring baris per unit.

Tiga hal ditegakkan di guard_db_access (di atas VPD Oracle di
oracle/03-row-scope.sql):
  1. PUBLIC (anonim) DITOLAK - tool basis data tak jalan.
  2. Sebelum SQL model, konteks penyaring-baris disetel dari identitas
     TERVERIFIKASI (set_identity NIP / set_operator), lalu SQL model jalan.
  3. SQL model divalidasi SELECT-tunggal - supaya ia tak bisa memanggil
     rag_scope untuk mengganti konteks penyaring itu sendiri.

Diuji tanpa MCP/Oracle: tool dalam diganti fake yang MEREKAM setiap SQL.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from ragcore.agent.hybrid import _is_safe_select, guard_db_access
from ragcore.agent.tools_hybrid import ACTIVE_USER
from ragcore.domain.users import PUBLIC, REGISTRY


class _SqlArgs(BaseModel):
    sql: str = ""


class _FakeTool:
    name = "sql_run"
    description = "jalankan SQL"
    args_schema = _SqlArgs

    def __init__(self):
        self.sqls: list[str] = []

    async def ainvoke(self, kwargs):
        self.sqls.append(kwargs["sql"])
        return "HASIL SQL"


# ---------------------------------------------------- penolakan & scope

def test_tool_db_menolak_publik():
    inner = _FakeTool()
    guarded = guard_db_access(inner)
    ACTIVE_USER.set(PUBLIC)
    out = asyncio.run(guarded.ainvoke({"sql": "SELECT * FROM ncs.v_karyawan"}))
    assert "DITOLAK" in out
    assert inner.sqls == []                    # tak ada SQL yang jalan


def test_user_menyetel_scope_nip_lalu_query():
    inner = _FakeTool()
    guarded = guard_db_access(inner)
    nip = next(iter(REGISTRY))
    ACTIVE_USER.set(REGISTRY[nip])
    out = asyncio.run(guarded.ainvoke({"sql": "SELECT nama FROM ncs.v_karyawan"}))
    assert out == "HASIL SQL"
    # Dua SQL: setel konteks identitas DULU, lalu SELECT model.
    assert len(inner.sqls) == 2
    assert f"set_identity('{nip}')" in inner.sqls[0]
    assert inner.sqls[1] == "SELECT nama FROM ncs.v_karyawan"


def test_operator_none_menyetel_scope_all():
    inner = _FakeTool()
    guarded = guard_db_access(inner)
    ACTIVE_USER.set(None)
    asyncio.run(guarded.ainvoke({"sql": "SELECT * FROM ncs.v_cuti"}))
    assert "set_operator" in inner.sqls[0]     # operator -> lihat semua
    assert inner.sqls[1] == "SELECT * FROM ncs.v_cuti"


# ---------------------------------------------------- validasi SELECT-only

def test_sql_non_select_ditolak():
    inner = _FakeTool()
    guarded = guard_db_access(inner)
    ACTIVE_USER.set(REGISTRY[next(iter(REGISTRY))])
    # Upaya model mengganti konteks -> ditolak, TAK ADA SQL yang jalan.
    out = asyncio.run(guarded.ainvoke(
        {"sql": "BEGIN ncs.rag_scope.set_operator; END;"}))
    assert "DITOLAK" in out
    assert inner.sqls == []


def test_validasi_select_only():
    assert _is_safe_select("SELECT * FROM ncs.v_karyawan")
    assert _is_safe_select("  with x as (select 1 from dual) select * from x")
    assert not _is_safe_select("BEGIN ncs.rag_scope.set_operator; END;")
    assert not _is_safe_select("SELECT 1 FROM dual; DROP TABLE ncs.karyawan")
    assert not _is_safe_select("EXEC ncs.rag_scope.set_identity('NCS-0001')")
    assert not _is_safe_select("")
