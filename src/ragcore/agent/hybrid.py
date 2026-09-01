"""Agent hibrida: dokumen lewat retrieval, basis data lewat MCP (L9).

Tool basis data TIDAK ditulis di sini. Ia datang dari server MCP resmi
Oracle (SQLcl), dan itulah inti pelajarannya: tool yang tidak kita tulis,
tidak kita pelihara, dan bisa dipakai kerangka kerja lain tanpa ditulis
ulang.

Konsekuensinya ikut dipelajari - nama dan deskripsi tool itu ditentukan
pihak lain dan BERUBAH antarversi. Karena itu evaluation/hybrid.py
mencocokkan nama tool secara longgar, bukan persis.

Jalankan:
    python -m ragcore.agent.hybrid "Apakah cuti Budi Santoso sesuai SOP?"
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from ragcore import config
from ragcore.agent.tools_hybrid import ACTIVE_USER, SYSTEM_PROMPT, search_rules
from ragcore.errors import SqlclMissing
from ragcore.log import get_logger
from ragcore.model import get_llm

log = get_logger(__name__)


def mcp_command() -> list[str]:
    """Perintah untuk menjalankan server MCP Oracle.

    Tiga cara, dari yang paling disukai:

      1. MCP_COMMAND diisi sendiri  -> dipakai apa adanya
      2. SQLCL_HOME diisi            -> java + jar, melewati skrip peluncur
      3. selain itu                  -> `sql -mcp` dari PATH

    Cara 2 ada karena skrip peluncur SQLcl menuntut konsol interaktif dan
    gagal dengan "java.io.IOException: Incorrect function" bila dijalankan
    tanpa TTY - padahal mode -mcp berkomunikasi lewat stdio berpipa dan
    tidak butuh konsol sama sekali. Diuji pada SQLcl 26.2.
    """

    if os.getenv("MCP_COMMAND"):
        return config.MCP_COMMAND

    if config.SQLCL_HOME:
        return [
            "java",
            # Dua flag ini disalin dari skrip peluncur SQLcl sendiri.
            # Tanpa keduanya: InaccessibleObjectException di java.util.prefs.
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "--add-opens=java.prefs/java.util.prefs=ALL-UNNAMED",
            "-cp", str(Path(config.SQLCL_HOME) / "lib" / "*"),
            "oracle.dbtools.raptor.scriptrunner.cmdline.SqlCli",
            "-mcp",
        ]

    # Diperiksa DI SINI, bukan dibiarkan gagal saat proses diluncurkan:
    # kegagalannya terjadi di dalam asyncio dan pesannya tidak menyebut
    # berkas apa yang dicari.
    if shutil.which("sql") is None:
        raise SqlclMissing("sql")
    return ["sql", "-mcp"]


def mcp_text(result) -> str:
    """Ambil teks dari hasil tool MCP.

    Hasilnya berupa daftar blok konten ({"type": "text", "text": ...}),
    bukan string. Mencetaknya apa adanya menghasilkan dump JSON yang tidak
    terbaca - dan itu yang pertama dilihat peserta saat menjalankan lab.

    Tinggal di sini, bukan di commands/, karena inilah lapisan yang berbicara
    dengan MCP. Ketika ia masih di commands/, agent/ terpaksa mengimpor dari
    commands/ - arah yang terbalik, dan siklus yang memaksa tiga impor
    ditunda ke dalam fungsi hanya supaya bisa dijalankan.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("text", result))
    if isinstance(result, (list, tuple)):
        return "\n".join(mcp_text(b) for b in result)
    return str(result)


def _mcp_config() -> dict:
    """Setelan server MCP Oracle.

    stdio, bukan HTTP: servernya berjalan sebagai proses anak di mesin yang
    sama. Untuk lab itu justru yang diinginkan - tidak ada port terbuka,
    tidak ada yang perlu diamankan di jaringan.
    """
    command = mcp_command()
    return {
        "oracle": {
            "command": command[0],
            "args": command[1:],
            "transport": "stdio",
        },
    }


async def get_database_tools() -> list:
    """Ambil DAFTAR tool dari server MCP, tanpa menjaga sesi.

    Berguna untuk memeriksa apa yang disediakan server. TIDAK cukup untuk
    menjalankan agent — lihat database_session() dan alasannya di sana.
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        print("  langchain-mcp-adapters belum terpasang - jalan dokumen saja.")
        return []

    try:
        client = MultiServerMCPClient(_mcp_config())
        return await client.get_tools()
    except Exception as e:
        log.warning("Server MCP Oracle tidak terjangkau (%s). Periksa: "
                    "container hidup, `sql -mcp` bisa dijalankan manual.",
                    type(e).__name__)
        return []


def _truly_orphan(process) -> bool:
    """Apakah server MCP ini sudah kehilangan induknya.

    KENAPA PEMERIKSAAN INI WAJIB ADA.

    Versi pertama fungsi ini menghentikan SETIAP proses java yang menjalankan
    SqlCli -mcp, tanpa memeriksa siapa pemiliknya. Itu benar untuk sisa proses
    yang sudah mati - dan merusak untuk yang masih dipakai.

    Terjadi saat lab ini disusun, dan persis seperti yang selalu terjadi di
    lab ini: TANPA GALAT. Sebuah evaluasi penuh sedang berjalan di latar
    belakang ketika perintah lain dijalankan di terminal yang sama. Perintah
    itu memulai dirinya dengan membersihkan server yatim - dan menghentikan
    server milik evaluasi yang sedang hidup. Evaluasi itu terus berjalan,
    terus mencetak kemajuan, dan mulai saat itu setiap query basis datanya
    gagal. Angka yang dihasilkannya tidak berguna, dan tidak ada apa pun di
    keluarannya yang menandakan itu.

    Bahkan sambung-ulang tidak menolong di sini: yang hilang bukan sambungan
    basis data, melainkan seluruh proses servernya.

    Cara memeriksanya: server MCP adalah proses ANAK dari python yang
    menjalankan lab. Bila induknya masih hidup dan masih berupa python,
    server itu SEDANG DIPAKAI - bukan yatim.

    Percobaan pertama menambahkan syarat "ragcore muncul di baris perintah
    induk", dan syarat itu SALAH. Python yang dijalankan lewat `python -m`,
    `python -c`, atau masukan standar tidak memuat nama paket di baris
    perintahnya sama sekali - baris perintahnya hanya `python.exe -`. Server
    yang sedang dipakai pun tetap dinilai yatim, dan pemeriksaan yang
    dimaksudkan melindungi justru mengulang kerusakan yang sama.

    psutil.parent() sendiri sudah menangani daur ulang PID: ia membandingkan
    waktu pembuatan induk dan anak, sehingga PID yang dipakai ulang oleh
    proses lain tidak dianggap induk. Itu sudah cukup.
    """
    import psutil

    try:
        induk = process.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return True
    if induk is None:
        return True
    try:
        return not (induk.name() or "").lower().startswith("python")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return True


def cleanup_orphan_mcp(quiet: bool = False) -> int:
    """Hentikan server MCP SQLcl yang tertinggal hidup. Kembalikan jumlahnya.

    KENAPA PERLU, meski keluar normal TIDAK bocor.

    Server MCP adalah proses anak. Saat keluar normal, context manager
    menutupnya dengan benar - diverifikasi: nol proses tersisa setelah
    evaluasi 30 kasus yang selesai. Tetapi Ctrl-C dan penghentian paksa
    MENINGGALKANNYA hidup, dan evaluasi penuh memakan 51 menit: peserta
    pasti akan menghentikannya di tengah, cepat atau lambat.

    Akibatnya menumpuk DIAM-DIAM. Tiap server yatim adalah JVM ~1,4 GB.
    Terjadi saat lab ini disusun: dua penghentian meninggalkan tiga server,
    RAM bebas turun 6,9 -> 4,1 GB, model chat makin tumpah ke CPU, dan
    kasus yang tadinya 4 menit menjadi lewat batas waktu.

    Yang membuatnya berbahaya: angkanya makin buruk tiap kali dijalankan
    ulang, dan tidak ada satu pun errors yang menjelaskan kenapa. Orang akan
    menyimpulkan modelnya memburuk.
    """
    try:
        import psutil
    except ImportError:
        log.info("psutil belum terpasang - pembersihan MCP yatim dilewati.")
        return 0

    stopped = 0
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (p.info.get("name") or "").lower()
            if not name.startswith("java"):
                continue
            row = " ".join(p.info.get("cmdline") or [])
            if "SqlCli" not in row or "-mcp" not in row:
                continue
            if not _truly_orphan(p):
                continue
            p.terminate()
            stopped += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if stopped:
        log.info("%d server MCP yatim dihentikan (sisa proses yang berhenti "
                 "paksa).", stopped)
    return stopped


# Penanda bahwa sesi basis data sudah TIDAK HIDUP lagi.
#
# Semuanya datang sebagai TEKS BIASA di dalam hasil tool yang berhasil, bukan
# sebagai exception - jadi tidak ada yang bisa ditangkap dengan try/except.
_LOST_MARKER = (
    "not established",      # SQLcl: "Connection not established"
    "not connected",
    "no connection",
    "ORA-02399",            # melewati batas CONNECT_TIME pada profil
    "ORA-03113",            # end-of-file on communication channel
    "ORA-03114",            # not connected to ORACLE
    "ORA-01012",            # not logged on
)


def session_lost(text: str) -> bool:
    """Apakah hasil tool ini sebenarnya laporan bahwa sambungan sudah mati."""
    low = (text or "").lower()
    return any(t.lower() in low for t in _LOST_MARKER)


def wrap_reconnect(tool, connect):
    """Bungkus satu tool MCP agar menyambung ulang sekali bila sesi terputus.

    KENAPA PERLU, DAN KENAPA INI BUKAN SEKADAR KETANGGUHAN.

    Lapisan 3 pembatas Oracle (infra/oracle/02-restrictions.sql) memasang profil dengan
    CONNECT_TIME 60 - sesi rag_baca DIBUNUH setelah 60 menit. Itu memang
    disengaja: agent yang lupa menutup sambungan tidak boleh menggenggam sesi
    basis data produksi selamanya.

    Tetapi evaluasi penuh memakai SATU sesi MCP dari awal sampai akhir, dan
    dengan --ulang 2 ia berjalan lebih dari satu jam. Di menit ke-60 Oracle
    memutusnya, dan sejak saat itu setiap sql_run mengembalikan teks
    "Connection not established".

    YANG MEMBUATNYA BERBAHAYA: itu bukan errors. Tool-nya BERHASIL, isinya
    saja yang berupa laporan kegagalan. Agent membacanya, lalu menjawab
    dengan sopan "Koneksi ke basis data terputus, informasi tidak dapat
    diperiksa" - jawaban yang jujur, dinilai SALAH, dan tercatat sebagai
    kelemahan model.

    Terbukti di lab ini: seluruh kasus `aritmetika` mendapat 0%, empat jalan
    berturut-turut, dan terbaca persis seperti "model tidak bisa menghitung
    selisih tanggal". Yang sebenarnya terjadi: pembatas keamanan lab sendiri
    membunuh sambungannya di tengah jalan, satu jam setelah evaluasi dimulai.
    """
    from langchain_core.tools import StructuredTool


    async def _run(**kwargs):
        result = await tool.ainvoke(kwargs)
        if not session_lost(mcp_text(result)):
            return result
        print("  Sesi basis data terputus - menyambung ulang "
              "(lihat wrap_reconnect).")
        await connect()
        return await tool.ainvoke(kwargs)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=_run,
    )


_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_SQL_FORBIDDEN = (
    # Non-SELECT / PL-SQL / eskalasi scope.
    "begin", "declare", "call ", "execute ", "exec ", "dbms_",
    "grant ", "insert ", "update ", "delete ", "merge ",
    "alter ", "drop ", "create ", "rag_scope",
    # Hardening C-01 - referensi TABEL MENTAH (bukan view) dan KATALOG SISTEM.
    # Grant DB rag_baca sudah menutup ini (hanya SELECT atas 5 view; selain itu
    # ORA-00942), tetapi ini lapis kedua di aplikasi: ditolak lebih awal,
    # DICATAT, dan tak pernah menyentuh basis data. Bentuk terkualifikasi
    # "ncs.cuti" TIDAK muncul pada view "ncs.v_cuti" (ada "v_" di antaranya),
    # jadi aman dari false-positive terhadap kueri view yang sah.
    "ncs.karyawan", "ncs.cuti", "ncs.lembur", "ncs.pengadaan", "ncs.sppd",
    "sys.", "dba_", "v$", "gv$", "utl_", "owa_", "all_tab", "all_source",
    "all_users", "user_tab", "information_schema",
)
_NIP_OK = re.compile(r"^[A-Za-z0-9-]{1,16}$")


def _unsafe_reason(sql: str) -> str | None:
    """Sebab sebuah SQL DITOLAK, atau None bila ia SELECT tunggal yang aman.

    Mengembalikan SEBAB, bukan sekadar bool, supaya penolakan bisa DICATAT
    (hardening C-05): percobaan yang ditolak di lapis ini adalah peristiwa
    keamanan yang layak terlihat, bukan didiamkan.
    """
    s = (sql or "").strip().rstrip(";").strip()
    if not s or not _SELECT_ONLY.match(s):
        return "bukan SELECT/WITH tunggal"
    if ";" in s:                                   # sisa ; = banyak statement
        return "banyak pernyataan (;)"
    low = s.lower()
    for f in _SQL_FORBIDDEN:
        if f in low:
            return f"token terlarang: {f.strip()}"
    return None


def _is_safe_select(sql: str) -> bool:
    """SATU perintah SELECT, tanpa blok PL/SQL, pemisah statement, tabel mentah,
    atau katalog sistem.

    Ini batas keamanan lapis aplikasi: karena model HANYA boleh SELECT atas
    view yang diizinkan, ia tak bisa memanggil ncs.rag_scope untuk mengganti
    konteks penyaring, menulis, maupun mengintip tabel mentah/katalog. VPD dan
    grant DB tetap menegakkan di bawahnya - ini menutup jalurnya lebih awal.
    """
    return _unsafe_reason(sql) is None


def _scope_sql(person) -> str:
    """PL/SQL untuk menyetel konteks penyaring-baris dari identitas TERVERIFIKASI.

    None = operator/maintenance -> lihat semua (sejalan connection_for(None)).
    User -> unit diturunkan Oracle dari NIP-nya (lihat rag_scope.set_identity);
    NIP tak sah -> '-' -> NO_DATA_FOUND -> fail-closed (tak lihat apa pun).
    """
    if person is None:
        return "BEGIN ncs.rag_scope.set_operator; END;"
    nip = getattr(person, "nip", "") or ""
    if not _NIP_OK.fullmatch(nip):
        nip = "-"
    return f"BEGIN ncs.rag_scope.set_identity('{nip}'); END;"


def guard_db_access(tool, connect=None):
    """Bungkus tool basis data: TOLAK anonim + SARING BARIS per unit pemohon.

    PENEGAKAN, BUKAN PROMPT. Tool dokumen (search_rules) menurunkan PUBLIC ke
    'umum' lewat RLS; tool basis data butuh penjaga setara. Dua hal ditegakkan:

      1. PUBLIC (anonim web) DITOLAK - hanya dokumen umum untuknya.
      2. Sebelum SQL model jalan, konteks penyaring-baris Oracle disetel dari
         identitas TERVERIFIKASI (bukan dari SQL model), lalu VPD di
         infra/oracle/03-row-scope.sql menyaring tiap baris ke UNIT pemohon. Direksi
         dan operator melihat semua. SQL model divalidasi SELECT-tunggal supaya
         ia tak bisa mengganti konteks itu sendiri.

    RECONNECT + SCOPE DISATUKAN DI SINI (menggantikan wrap_reconnect untuk tool
    ini). Kalau sesi diputus profil sumber daya di antara setel-scope dan
    SELECT, menyambung ulang saja TIDAK cukup: sesi baru punya rag_ctx KOSONG,
    VPD memulangkan '1=0', dan query sah balik NOL BARIS diam-diam - persis
    kegagalan 'tool berhasil, jawaban salah' yang dijaga modul ini. Maka saat
    sesi terputus, scope DIPASANG ULANG lalu SELECT diulang, sebagai satu
    kesatuan. `connect=None` (mis. di tes) melewati pemulihan itu.

    Endpoint /agent/ask menolak PUBLIC lebih dulu (belt); ini lapisan kedua.
    """
    from langchain_core.tools import StructuredTool

    from ragcore.domain.users import PUBLIC

    async def _scope_then_query(person, kwargs):
        # Setel penyaring-baris dari identitas terverifikasi, LALU jalankan SQL.
        await tool.ainvoke({"sql": _scope_sql(person)})
        return await tool.ainvoke(kwargs)

    async def _run(**kwargs):
        # HANYA PUBLIC yang ditolak, BUKAN None: None = operator/maintenance
        # (tepercaya, seperti connection_for(None)); web anonim SELALU jadi
        # PUBLIC (bukan None) lewat _resolve_identity.
        person = ACTIVE_USER.get()
        if person is PUBLIC:
            # Peristiwa keamanan (hardening C-05): percobaan kueri basis data
            # tanpa identitas terverifikasi - dicatat, bukan didiamkan.
            log.warning("guard_db: TOLAK PUBLIC - kueri DB tanpa login")
            return ("DITOLAK: kueri basis data karyawan memerlukan login. "
                    "Tanpa identitas terverifikasi hanya dokumen berklasifikasi "
                    "umum yang dapat diakses.")
        sebab = _unsafe_reason(kwargs.get("sql", ""))
        if sebab is not None:
            # SQL yang ditolak validator adalah sinyal keamanan yang paling
            # berharga dicatat: ia menandai upaya menulis, blok PL/SQL, atau
            # menyentuh tabel mentah/katalog. Cuplikan disingkat agar log tak
            # membengkak.
            sql_cuplik = " ".join((kwargs.get("sql") or "").split())[:160]
            log.warning("guard_db: TOLAK SQL (%s) oleh %s | %s",
                        sebab, getattr(person, "nip", person), sql_cuplik)
            return ("DITOLAK: hanya SATU perintah SELECT atas view yang "
                    "diizinkan yang dijalankan di jalur ini - blok PL/SQL, "
                    "banyak-pernyataan, tabel mentah/katalog sistem, atau "
                    "perintah selain SELECT tidak diizinkan.")
        result = await _scope_then_query(person, kwargs)
        if connect is not None and session_lost(mcp_text(result)):
            await connect()
            result = await _scope_then_query(person, kwargs)   # scope ULANG
        return result

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=_run,
    )


@asynccontextmanager
async def database_session(quiet: bool = True, operator: bool = False):
    """Buka SATU sesi MCP, sambungkan ke basis data, hasilkan daftar tool.

    `operator=False` (bawaan) memakai koneksi PRODUKSI hak-minimal (rag_baca):
    hanya set_identity, set_operator ditolak DB. `operator=True` memakai koneksi
    OPERATOR (rag_operator) yang boleh 'lihat semua' - HANYA untuk jalur non-
    produksi (CLI, evaluasi). Lihat infra/oracle/04-operator-account.sql. Bila koneksi
    operator belum disiapkan, config menjatuhkannya ke koneksi rag_baca.

    SATU SESI ITU WAJIB, DAN INI JEBAKANNYA.

    `MultiServerMCPClient.get_tools()` membuka sesi BARU untuk setiap
    panggilan tool. Untuk server yang tanpa keadaan itu tidak masalah —
    tetapi server MCP Oracle MENYIMPAN sambungan basis datanya di sesi.
    Akibatnya:

        connect(agentlab)   -> "Successfully connected"   (sesi A)
        sql_run(SELECT ...) -> "Connection not established" (sesi B)

    Dua panggilan berurutan, dua sesi berbeda, dan sambungan yang baru saja
    dibuat sudah hilang. Tidak ada errors yang menyebut sesi sama sekali.

    Karena itu di sini dipakai klien.session(), yang menjaga satu sesi
    hidup selama context manager terbuka — dan `connect` dipanggil sekali
    di dalamnya.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools


    client = MultiServerMCPClient(_mcp_config())
    async with client.session("oracle") as session:
        tool = await load_mcp_tools(session)
        mapping = {a.name: a for a in tool}

        conn_name = (config.MCP_CONNECTION_OPERATOR if operator
                     else config.MCP_CONNECTION_NAME)

        async def connect():
            """Buka sambungan basis data pada sesi MCP yang sedang hidup."""
            if "connect" not in mapping:
                return None
            return await mapping["connect"].ainvoke(
                {"connection_name": conn_name})

        if "connect" in mapping:
            result = await connect()
            text = mcp_text(result)
            if not quiet:
                row = text.strip().splitlines()[:2]
                print("  " + " / ".join(b.strip() for b in row if b.strip()))
            if "not found" in text.lower() or "tidak" in text.lower():
                print(f"  Sambungan '{conn_name}' belum ada.")
                print("  Jalankan: python -m ragcore.commands.mcp "
                      "--simpan-sambungan")
        # Tool yang dipakai menjawab dibungkus agar tahan sesi yang
        # diputus profil sumber daya. Lihat wrap_reconnect().
        # Tool DB dibungkus guard_db_access, yang kini SEKALIGUS menangani
        # penyambungan ulang (reconnect + pasang-ulang scope + SELECT sebagai
        # satu kesatuan) - menggantikan wrap_reconnect untuk tool ini supaya
        # penyaring-baris tak hilang saat sesi diputus di tengah.
        yield [guard_db_access(a, connect)
               if a.name in USED_MCP_TOOL else a
               for a in tool]


# Tool MCP yang benar-benar dibutuhkan agent untuk MENJAWAB.
#
# Server MCP Oracle menyediakan sembilan tool, tetapi tujuh di antaranya
# mengurus SAMBUNGAN dan pemeliharaan: connect, disconnect, connections_list,
# skills_sync, annotation_generate, request_status, sqlcl_run. Semuanya sudah
# ditangani database_session() sebelum agent berjalan.
#
# KENAPA DISARING, bukan dibiarkan saja:
#
#   1. Deskripsi tool MCP MENYURUH model memanggilnya. connections_list
#      berbunyi "Call this tool when a connection name is not already known",
#      dan model menurut - membuang satu giliran penuh untuk informasi yang
#      tidak ia perlukan.
#   2. Sepuluh tool adalah permukaan pilihan yang lebar untuk model kecil.
#      Diuji dengan qwen3:4b: model mengeluarkan panggilan tool sebagai TEKS
#      JSON mentah, dengan nama argumen yang dikarang.
#
# Ini langsung mengenai metrik "ketepatan pemilihan alat" di L9: memperbaiki
# pilihan alat sering berarti MENGURANGI pilihannya, bukan memperbaiki prompt.
# schema_information SENGAJA TIDAK ADA DI SINI, meski ia terdengar berguna.
#
# Tool itu menjelaskan skema AKUN YANG TERSAMBUNG, dan akun agent (rag_baca)
# tidak memiliki satu objek pun - seluruh data ada di skema ncs, dan agent
# hanya diberi hak SELECT atas lima view di sana. Diuji langsung, hasilnya:
#
#     Basic Schema Objects Listing:
#     "OWNER","OBJECT_TYPE","OBJECT_NAME"
#
# Judul kolom, nol baris. Itu konsekuensi langsung lapisan 1 pembatas Oracle,
# bukan kerusakan.
#
# MASALAHNYA BUKAN TOOL-NYA TIDAK BERGUNA, MELAINKAN KOSONGNYA MENYESATKAN.
# Daftar kosong terbaca oleh model sebagai "tidak ada tabel apa pun", dan dari
# situ ia menyimpulkan datanya memang tidak ada. Terbukti dengan qwen3:8b pada
# kasus `agregat`: model memanggil schema_information, menerima nol baris,
# lalu menjawab "Informasi ini tidak ditemukan dalam dokumen yang tersedia" -
# padahal kelima view-nya ada, berisi, dan bisa dibaca detik itu juga.
#
# Skemanya sudah diberikan langsung lewat SKEMA_BASIS_DATA di prompt sistem,
# jadi tidak ada yang hilang dengan mencabutnya. Yang hilang justru sebuah
# jalan buntu yang tampak seperti jawaban.
USED_MCP_TOOL = ("sql_run",)


def filter_tools(db_tools: list, used: tuple[str, ...] = USED_MCP_TOOL) -> list:
    """Sisakan hanya tool MCP yang dibutuhkan untuk menjawab."""
    return [a for a in db_tools if a.name in used]


@asynccontextmanager
async def hybrid_agent(quiet: bool = False, tool_all: bool = False,
                        person=None, operator: bool = False):
    """Agent dengan tool dokumen + tool basis data, di dalam satu sesi MCP.

    `semua_alat=True` mematikan penyaringan — berguna di kelas untuk
    memperagakan sendiri apa yang terjadi pada permukaan tool yang lebar.

    `operator=True` memakai koneksi rag_operator (boleh 'lihat semua') - untuk
    jalur non-produksi seperti evaluasi/CLI yang menjalankan kasus tanpa login.
    """
    from langchain.agents import create_agent


    # Dipasang di sini, bukan di dalam tool: satu tempat, dan berlaku untuk
    # SELURUH pemanggilan tool selama agent ini hidup.
    ACTIVE_USER.set(person)

    async with database_session(quiet=quiet, operator=operator) as db_tools:
        used = db_tools if tool_all else filter_tools(db_tools)
        if not quiet:
            print(f"  {len(used)} dari {len(db_tools)} tool MCP dipakai: "
                  f"{[a.name for a in used]}")
            print("  + 1 tool dokumen (search_rules)")
        yield create_agent(
            model=get_llm(),
            tools=[search_rules, *used],
            system_prompt=SYSTEM_PROMPT,
        )


async def _main(question: str, person=None) -> None:
    # ADAPTER PRESENTASI di atas AgentService.
    #
    # Orkestrasi (sesi MCP, identitas, guard keluaran) sekarang di
    # application/agent_service.py, dengan dependency disuntik. Fungsi ini
    # tinggal mencetak: langkah perantara sebagai diagnosis, lalu jawaban
    # akhir yang sudah disaring.
    from ragcore.application import build_agent_service

    # CLI = jalur pemeliharaan/operator (person bawaannya None -> 'lihat
    # semua'), jadi koneksi operator. Produksi /agent/ask tetap rag_baca.
    outcome = await build_agent_service(quiet=False, operator=True).ask_once(
        question, identity=person)

    for message in outcome.steps:
        message.pretty_print()
    print("\n  Jawaban:")
    print(f"  {outcome.answer}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(_main(" ".join(sys.argv[1:])))
