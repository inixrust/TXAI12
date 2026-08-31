"""Penyiapan server MCP Oracle (L7, L8).

    python -m ragcore.commands.mcp --alat               # daftar tool server
    python -m ragcore.commands.mcp --simpan-sambungan   # sekali per mesin (rag_baca)
    python -m ragcore.commands.mcp --simpan-operator    # akun operator (rag_operator)
    python -m ragcore.commands.mcp --uji                # connect + satu query

KENAPA --simpan-sambungan ADA. Tool `connect` pada server MCP hanya menerima
NAMA sambungan tersimpan — ia tidak bisa diberi user dan sandi. Tanpa
sambungan tersimpan, agent punya tool tetapi tidak punya basis data.

Cara resminya `sql /nolog` lalu `conn -save`, dan itu MENUNTUT terminal
sungguhan: dijalankan tanpa TTY, skrip peluncur SQLcl gagal dengan
"java.io.IOException: Incorrect function". Perintah di sini menyimpannya
lewat server MCP itu sendiri, yang tidak butuh konsol sama sekali.
"""
from __future__ import annotations

import asyncio
import sys

from ragcore import config
from ragcore.agent.hybrid import (
    database_session,
    get_database_tools,
    mcp_text,
)


async def _list_tools() -> int:

    tool = await get_database_tools()
    if not tool:
        return 1
    print(f"\n  {len(tool)} tool disediakan server MCP Oracle:\n")
    for a in sorted(tool, key=lambda x: x.name):
        print(f"    {a.name:22} {(a.description or '').strip().splitlines()[0][:66]}")
    return 0


async def _save_connection(operator: bool = False) -> int:

    # operator=True menyimpan sambungan AKUN OPERATOR (rag_operator) yang boleh
    # 'lihat semua' - dipakai CLI/evaluasi. Bawaannya menyimpan akun query
    # produksi (rag_baca). Lihat oracle/04-operator-account.sql.
    name = (config.MCP_CONNECTION_OPERATOR if operator
            else config.MCP_CONNECTION_NAME)
    creds = (config.ORACLE_CONNECTION_OPERATOR if operator
             else config.ORACLE_CONNECTION)
    commands = f"conn -save {name} -savepwd {creds}"
    print(f"  menyimpan sambungan '{name}' sebagai {creds.split('/')[0]}")

    # Sesi dibuka dengan koneksi bawaan (rag_baca yang sudah ada); sqlcl_run
    # hanya perlu sesi MCP hidup untuk menjalankan `conn -save`, bukan koneksi
    # yang sedang disimpan itu sendiri.
    async with database_session(quiet=True) as tool:
        mapping = {a.name: a for a in tool}
        if "sqlcl_run" not in mapping:
            print("  Server MCP tidak menyediakan sqlcl_run.")
            return 1
        result = mcp_text(await mapping["sqlcl_run"].ainvoke({"sqlcl": commands}))
        for row in result.splitlines():
            if row.strip() and "mouse" not in row:
                print("   ", row.strip()[:90])
        stored = mcp_text(await mapping["connections_list"].ainvoke({}))
        exists = name in stored
        print(f"\n  terdaftar sekarang: {'YA' if exists else 'TIDAK'}")
        return 0 if exists else 1


async def _test() -> int:

    query = "SELECT COUNT(*) AS jml FROM ncs.v_pengadaan"
    async with database_session(quiet=False) as tool:
        mapping = {a.name: a for a in tool}
        print(f"\n  {query}")
        result = mcp_text(await mapping["sql_run"].ainvoke({"sql": query}))
        for row in result.splitlines():
            if row.strip():
                print("   ", row.strip()[:90])
        return 0 if "not established" not in result else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--alat" in argv:
        return asyncio.run(_list_tools())
    if "--simpan-sambungan" in argv:
        return asyncio.run(_save_connection())
    if "--simpan-operator" in argv:
        return asyncio.run(_save_connection(operator=True))
    if "--uji" in argv:
        return asyncio.run(_test())
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
