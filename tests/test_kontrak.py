"""Tes kontrak: yang menangkap kerusakan refactor TANPA butuh model hidup.

Setiap tes di berkas ini dipilih karena satu alasan: cacat yang ia periksa
PERNAH LOLOS ke dalam lab ini, dan tidak ada yang memberi tahu. Impor tetap
berhasil, `compileall` tetap OK, aplikasi tetap menyala. Yang rusak hanya
ketahuan saat seseorang kebetulan menjalankan jalur itu.

Semuanya berjalan dalam hitungan detik dan tidak menyentuh Ollama, Postgres,
maupun Oracle. Jalankan sebelum menyerahkan perubahan apa pun:

    python -m pytest tests/ -q
"""
from __future__ import annotations

import ast
import importlib
import json
import pkgutil
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
PAKET = SRC / "ragcore"


def _modul_python():
    return [p for p in PAKET.rglob("*.py") if "__pycache__" not in p.parts]


# --------------------------------------------------------------------------
# 1. Seluruh modul harus bisa diimpor.
#    Menangkap: IndentationError, impor melingkar, nama modul yang berubah.
# --------------------------------------------------------------------------
def test_semua_modul_terimpor():
    import ragcore

    gagal = []
    for m in pkgutil.walk_packages(ragcore.__path__, "ragcore."):
        try:
            importlib.import_module(m.name)
        except Exception as e:
            gagal.append(f"{m.name}: {type(e).__name__}: {e}")
    assert not gagal, "modul gagal diimpor:\n  " + "\n  ".join(gagal)


# --------------------------------------------------------------------------
# 2. __all__ tidak boleh menyebut nama yang tidak ada.
#    Menangkap: `from paket import *` -> AttributeError setelah rename.
#    PERNAH TERJADI: 26 nama Indonesia pra-refactor tertinggal di __all__.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("pkg", [
    "agent", "commands", "evaluation", "extraction", "flow", "generation",
    "indexing", "ingest", "model", "retrieval", "storage", "vectorless",
])
def test_all_hanya_menyebut_nama_yang_ada(pkg):
    m = importlib.import_module(f"ragcore.{pkg}")
    hilang = [n for n in getattr(m, "__all__", []) if not hasattr(m, n)]
    assert not hilang, f"ragcore.{pkg}.__all__ menyebut nama tak ada: {hilang}"


# --------------------------------------------------------------------------
# 3. argparse: setiap args.X yang dibaca harus benar-benar terdaftar.
#    PERNAH TERJADI: answer/search/agent/index/load semuanya mati dengan
#    AttributeError karena dest diganti tapi pembacanya tidak.
# --------------------------------------------------------------------------
def _dest_dan_baca(path: Path):
    t = ast.parse(path.read_text(encoding="utf-8"))
    daftar, baca = set(), {}
    for n in ast.walk(t):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_argument"):
            eksplisit = next((k.value.value for k in n.keywords
                              if k.arg == "dest" and isinstance(k.value, ast.Constant)), None)
            if eksplisit:
                daftar.add(eksplisit)
            else:
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        daftar.add(a.value.lstrip("-").replace("-", "_"))
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "args"):
            baca.setdefault(n.attr, n.lineno)
    return daftar, baca


@pytest.mark.parametrize("path", sorted((PAKET / "commands").glob("*.py")),
                         ids=lambda p: p.name)
def test_argparse_dest_cocok_dengan_pembacanya(path):
    daftar, baca = _dest_dan_baca(path)
    if not daftar:
        pytest.skip("tidak memakai argparse")
    # "question" didaftarkan oleh pembantu bersama di _args.py
    daftar |= {"question"}
    salah = {k: ln for k, ln in baca.items() if k not in daftar}
    assert not salah, (
        f"{path.name}: args.{list(salah)} dibaca tapi tidak terdaftar "
        f"(terdaftar: {sorted(daftar)})")


# --------------------------------------------------------------------------
# 4. Kunci State LangGraph yang dibaca simpul harus ada di skema.
#    PERNAH TERJADI: 8 dari 10 kunci tidak cocok -> graf L10 mati total,
#    dan tidak satu pun audit menyadarinya.
# --------------------------------------------------------------------------
def test_kunci_state_langgraph_cocok():
    from ragcore.flow import production

    skema = set(production.State.__annotations__)
    sumber = (PAKET / "flow" / "production.py").read_text(encoding="utf-8")
    t = ast.parse(sumber)

    dipakai = set()
    for n in ast.walk(t):
        # state.get("x") dan state["x"]
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "state"):
            dipakai.add(n.args[0].value)
        if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                and n.value.id == "state" and isinstance(n.slice, ast.Constant)):
            dipakai.add(n.slice.value)

    asing = dipakai - skema
    assert not asing, f"simpul membaca kunci di luar skema State: {sorted(asing)}"


# --------------------------------------------------------------------------
# 5. Nama GUC hanya boleh berasal dari SATU tempat.
#    PERNAH TERJADI: config.py memakai app.unit_pengguna sementara
#    pgvector.py memakai app.unit_users -> RLS diam-diam berhenti menyaring
#    dan peragaannya mencetak tiga angka identik sambil berkata "berbeda".
# --------------------------------------------------------------------------
def test_nama_guc_tidak_ditulis_ulang_sebagai_literal():
    from ragcore import config

    # database.py adalah tempat GUC_UNIT DIDEFINISIKAN; config.py mengekspornya
    # ulang. Keduanya boleh menyebut literalnya - yang dilarang adalah menulis
    # ulang literal itu di modul LAIN alih-alih memakai config.GUC_UNIT.
    pendefinisi = {"config.py", "database.py"}
    pelanggar = []
    for p in _modul_python():
        if p.name in pendefinisi:
            continue
        isi = p.read_text(encoding="utf-8")
        for literal in (f"'{config.GUC_UNIT}'", f'"{config.GUC_UNIT}"',
                        "'app.unit_users'", '"app.unit_users"'):
            if literal in isi:
                pelanggar.append(f"{p.name}: {literal}")
    assert not pelanggar, (
        "nama GUC ditulis sebagai literal, bukan lewat config.GUC_UNIT — "
        "inilah yang dulu mematikan RLS tanpa satu pun galat:\n  "
        + "\n  ".join(pelanggar))


# --------------------------------------------------------------------------
# 6. Prompt WAJIB tetap berbahasa Indonesia.
#    Menangkap: refactor istilah yang bocor ke dalam teks prompt.
# --------------------------------------------------------------------------
def test_prompt_tetap_bahasa_indonesia():
    from ragcore.agent.tools_hybrid import SYSTEM_PROMPT
    from ragcore.retrieval.self_query import PROMPT

    nyasar = ("filtering", "chunking", "the ", " you ", "retrieval of",
              "storage", "worker", "queue")
    for nama, teks in (("SYSTEM_PROMPT", SYSTEM_PROMPT), ("self_query.PROMPT", PROMPT)):
        rendah = teks.lower()
        ketemu = [w for w in nyasar if w in rendah]
        assert not ketemu, f"{nama} mengandung istilah Inggris nyasar: {ketemu}"


# --------------------------------------------------------------------------
# 7. Nama alat yang dilihat model harus konsisten di kode, guard, dan set uji.
#    PERNAH TERJADI: cari_ketentuan -> search_rules memutus guard.py dan
#    testset_hybrid.json, dan baru ketahuan dari komentar yang basi.
# --------------------------------------------------------------------------
def test_nama_alat_konsisten_dengan_set_uji():
    import json

    from ragcore.agent.tools_hybrid import search_rules

    nama = search_rules.name
    guard = (PAKET / "domain" / "guard.py").read_text(encoding="utf-8")
    assert nama in guard, f"guard.py tidak menyebut alat '{nama}'"

    uji = json.loads((SRC.parent / "testset_hybrid.json").read_text(encoding="utf-8"))
    kasus = uji if isinstance(uji, list) else uji.get("kasus", uji.get("cases", []))
    disebut = {a for k in kasus for a in (k.get("alat_wajib_dipanggil") or [])}
    asing = {a for a in disebut if a.startswith(("cari_", "search_"))} - {nama}
    assert not asing, f"set uji menyebut alat dokumen yang tidak ada: {asing}"


# --------------------------------------------------------------------------
# 8. Kedua storage HARUS memenuhi kontrak VectorStore yang sama.
#    Sebelumnya kontrak ini hanya berupa kalimat di docstring, dan kalimat
#    itu keliru: menyebut as_retriever() yang tak pernah dipakai, dan
#    melewatkan add_documents() yang dipakai.
# --------------------------------------------------------------------------
def test_kontrak_storage_disebut_lengkap():
    """Setiap metode di Protocol harus benar-benar dipanggil di kode.

    Kontrak yang lebih lebar dari pemakaian akan menolak implementasi ketiga
    tanpa alasan. Tes ini menjaga Protocol tetap sesempit kenyataannya.
    """
    from ragcore.storage.select import VectorStore

    metode = [m for m in VectorStore.__protocol_attrs__ if not m.startswith("_")]
    sumber = "\n".join(p.read_text(encoding="utf-8") for p in _modul_python())
    tak_dipakai = [m for m in metode if f".{m}(" not in sumber]
    assert not tak_dipakai, (
        f"Protocol VectorStore menuntut {tak_dipakai} tapi tidak ada yang "
        f"memanggilnya — kontraknya lebih lebar daripada kenyataan")


@pytest.mark.lambat
def test_kedua_storage_memenuhi_kontrak():
    from ragcore.indexing.artifacts import open_index
    from ragcore.storage import pgvector
    from ragcore.storage.select import VectorStore

    for nama, store in (("pgvector", pgvector.open_store()),
                        ("chroma", open_index())):
        assert isinstance(store, VectorStore), (
            f"{nama} tidak memenuhi VectorStore — pipeline retrieval akan "
            f"gagal pada STORAGE={nama}")


# --------------------------------------------------------------------------
# 9. connection_for() adalah batas kepercayaan menuju URL Postgres.
#    Nilai unit yang mengandung '&' bisa menyuntik parameter libpq tambahan,
#    dan parameter kueri libpq MENIMPA kredensial di URL — jalan menuju
#    sambungan pemilik tabel yang kebal RLS. Harus fail-closed.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("jahat", [
    "Divisi TI&application_name=x",           # parameter libpq kedua
    "X&user=rag&password=rahasia",            # menimpa kredensial -> pemilik
    "X&options=-c app.unit_pengguna%3DTI",    # menimpa GUC unit lain
    "unit\nDivisi TI",                        # baris baru
    "",                                       # kosong
    "%2F",                                    # sudah ter-encode
])
def test_connection_for_menolak_injeksi(jahat):
    from ragcore.domain.users import User, connection_for

    orang = User("X", "Penyerang", jahat, "staf")
    with pytest.raises(ValueError):
        connection_for(orang)


def test_connection_for_menerima_unit_wajar():
    from ragcore.domain.users import User, connection_for

    for unit in ("Divisi TI", "Divisi SDM", "Direksi", "Divisi Pengadaan"):
        url = connection_for(User("X", "N", unit, "staf"))
        assert "&" not in url.split("?", 1)[1], f"'{unit}' menghasilkan '&' di query"
        assert "application_name" not in url


# --------------------------------------------------------------------------
# 10. Reset fts_query bergantung pada nama internal PGVectorStore. Kalau nama
#     itu hilang di upgrade, _wrap_fts() harus GAGAL KERAS - bukan diam-diam
#     mengembalikan store yang hybrid search-nya memburuk tanpa galat.
# --------------------------------------------------------------------------
def test_wrap_fts_gagal_keras_bila_internal_hilang():
    from ragcore.storage import pgvector

    class TanpaInternal:
        def similarity_search(self, *a, **k):
            return []

    with pytest.raises(RuntimeError, match="Struktur internal PGVectorStore"):
        pgvector._wrap_fts(TanpaInternal())


# --------------------------------------------------------------------------
# 11. chunks disimpan sebagai JSON, BUKAN pickle. pickle.load menjalankan kode
#     apa pun di dalam berkasnya; untuk data teks itu risiko tanpa imbalan.
# --------------------------------------------------------------------------
def test_chunks_disimpan_sebagai_json(tmp_path, monkeypatch):
    from langchain_core.documents import Document

    from ragcore import config
    from ragcore.indexing import artifacts

    berkas = tmp_path / "chunks.json"
    monkeypatch.setattr(config, "CHUNKS_FILE", berkas)

    asli = [Document(page_content="isi satu", metadata={"source": "a.pdf", "page": None}),
            Document(page_content="isi dua", metadata={"unit": "Divisi TI"})]
    artifacts.save_chunks(asli)

    # Berkasnya harus JSON yang bisa dibaca manusia dan pustaka lain - bukan
    # biner pickle. json.loads() akan gagal bila formatnya pickle.
    diurai = json.loads(berkas.read_text(encoding="utf-8"))
    assert diurai[0]["page_content"] == "isi satu"

    kembali = artifacts.load_chunks()
    assert [d.page_content for d in kembali] == ["isi satu", "isi dua"]
    assert kembali[1].metadata["unit"] == "Divisi TI"


def test_load_chunks_menolak_format_lama(tmp_path, monkeypatch):
    from ragcore import config
    from ragcore.errors import IndexNotBuilt
    from ragcore.indexing import artifacts

    berkas = tmp_path / "chunks.json"
    berkas.write_bytes(b"\x80\x04\x95")   # magic pickle, bukan JSON
    monkeypatch.setattr(config, "CHUNKS_FILE", berkas)

    with pytest.raises(IndexNotBuilt, match=r"bangun ulang|JSON"):
        artifacts.load_chunks()


# --------------------------------------------------------------------------
# 12. Diagnostik operator lewat logging (level, nama modul, stderr) - TERPISAH
#     dari keluaran produk yang tetap di stdout.
# --------------------------------------------------------------------------
def test_logger_terpisah_dari_stdout():
    """Kontrak: diagnostik operator ke stderr (bukan stdout), dan tidak
    bocor ke root logger yang mungkin dikonfigurasi pihak lain."""
    import sys

    from ragcore.log import get_logger

    log = get_logger("ragcore.uji_test")
    root = log.parent if log.name == "ragcore.uji_test" else log
    # naik sampai logger paket 'ragcore'
    while root.name != "ragcore" and root.parent is not None:
        root = root.parent

    assert root.handlers, "logger paket harus punya handler sendiri"
    streams = [getattr(h, "stream", None) for h in root.handlers]
    assert sys.stderr in streams or any(
        getattr(s, "name", "") == "<stderr>" for s in streams if s), \
        "diagnostik harus ke stderr, bukan stdout milik keluaran produk"
    assert root.propagate is False, \
        "tidak boleh naik ke root global yang dikonfigurasi pihak lain"


# --------------------------------------------------------------------------
# 13. Modul yang dipecah (evaluation) tidak boleh membentuk siklus impor yang
#     pecah bergantung urutan. Impor SETIAP submodul lebih dulu, sendiri-
#     sendiri, di subprocess bersih - kalau salah satu urutan meledak, itu
#     siklus yang cuma tersembunyi oleh urutan impor kebetulan.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("modul", [
    "ragcore.evaluation.hybrid",
    "ragcore.evaluation.reporting",
    "ragcore.evaluation.scoring",
])
def test_submodul_evaluation_bebas_siklus(modul):
    import subprocess
    import sys

    env = {**__import__("os").environ, "PYTHONPATH": str(SRC), "STORAGE": "chroma"}
    r = subprocess.run(
        [sys.executable, "-c", f"import {modul}"],
        capture_output=True, text=True, env=env, timeout=90)
    assert r.returncode == 0, (
        f"impor '{modul}' lebih dulu gagal — kemungkinan siklus impor:\n"
        f"{r.stderr[-500:]}")


# --------------------------------------------------------------------------
# 14. config adalah FASAD atas paket settings/. Setiap nama publik yang dulu
#     ada padanya harus tetap ada - 8 subpaket mengaksesnya lewat config.X,
#     dan memecah config tidak boleh memecah satu pun dari mereka.
# --------------------------------------------------------------------------
def test_config_fasad_mempertahankan_kontrak():
    from ragcore import config

    # Nama yang BENAR-BENAR diakses lewat config.X di seluruh basis kode.
    # Batas (?<![\w.]) mencegah cocok di tengah pengenal lain, mis.
    # `hybrid_search_config.fts_query` yang bukan akses ke modul config.
    dipakai = set()
    pola = __import__("re").compile(r"(?<![\w.])config\.([A-Za-z_][A-Za-z0-9_]*)")
    for p in _modul_python():
        for m in pola.finditer(p.read_text(encoding="utf-8")):
            dipakai.add(m.group(1))

    # buang yang jelas bukan atribut config (mis. config.py di komentar)
    dipakai -= {"py"}
    hilang = [n for n in dipakai if not hasattr(config, n)]
    assert not hilang, (
        f"config tidak lagi menyediakan {hilang} — fasad memecah kode yang "
        f"mengaksesnya lewat config.X")


def test_settings_stdlib_only():
    """settings dan config harus tetap bisa diimpor tanpa paket berat -
    check.py membacanya SEBELUM memastikan langchain dkk terpasang."""
    import subprocess
    import sys

    kode = (
        "import sys; from ragcore import config; "
        "berat=[m for m in sys.modules if m.split('.')[0] in "
        "('langchain','torch','langgraph','psycopg','chromadb')]; "
        "print('BERAT' if berat else 'BERSIH')"
    )
    env = {**__import__("os").environ, "PYTHONPATH": str(SRC), "STORAGE": "chroma"}
    r = subprocess.run([sys.executable, "-c", kode],
                       capture_output=True, text=True, env=env, timeout=60)
    assert "BERSIH" in r.stdout, f"config menarik paket berat:\n{r.stdout}{r.stderr[-300:]}"


# --------------------------------------------------------------------------
# 15. Anti-corruption layer: tipe data framework hanya lewat ragcore.domain,
#     konstruksi model hanya lewat ragcore.model. Menembusnya langsung dari
#     modul lain membuat satu bump versi langchain merembet ke belasan berkas -
#     tepat yang lapisan ini cegah.
# --------------------------------------------------------------------------
def test_document_hanya_lewat_domain():
    # domain/types.py adalah seam itu sendiri - satu-satunya yang boleh
    # menyentuh langchain_core secara langsung.
    seam = {("domain", "types.py")}
    pelanggar = []
    for p in _modul_python():
        if p.parts[-2:] in seam:
            continue
        isi = p.read_text(encoding="utf-8")
        if "from langchain_core.documents import" in isi:
            pelanggar.append(p.name)
        if "from langchain_core.messages import" in isi:
            pelanggar.append(f"{p.name} (messages)")
    assert not pelanggar, (
        "tipe langchain_core diimpor langsung, bukan lewat ragcore.domain: "
        f"{pelanggar}")


def test_model_dibangun_hanya_di_provider():
    """Konstruksi ChatOllama/OllamaEmbeddings adalah seam. Hanya provider.py
    yang boleh menyentuh pustaka model langsung."""
    import re

    pola = re.compile(r"\b(ChatOllama|OllamaEmbeddings)\s*\(")
    impor = re.compile(r"import\s+(ChatOllama|OllamaEmbeddings)")
    pelanggar = []
    for p in _modul_python():
        if p.parts[-2:] == ("model", "provider.py") or p.name == "provider.py":
            continue
        isi = p.read_text(encoding="utf-8")
        if pola.search(isi) or impor.search(isi):
            pelanggar.append(p.name)
    assert not pelanggar, (
        f"model dibangun di luar seam model/provider.py: {pelanggar}")


# --------------------------------------------------------------------------
# 16. Arah lapisan: domain/ adalah inti, tidak boleh bergantung pada lapisan
#     di ATASNYA (commands, ui, flow, agent) maupun pada konstruksi framework
#     berat. Kalau domain mulai mengimpor commands, arah ketergantungan
#     terbalik dan "inti" berhenti menjadi inti.
# --------------------------------------------------------------------------
def test_domain_tidak_bergantung_ke_lapisan_atas():
    atas = ("commands", "ui", "ui12", "flow", "agent", "vectorless",
            "evaluation", "application")
    pelanggar = []
    for p in (PAKET / "domain").glob("*.py"):
        t = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(t):
            mod = None
            if isinstance(n, ast.ImportFrom):
                mod = n.module or ""
            elif isinstance(n, ast.Import):
                mod = n.names[0].name
            if not mod:
                continue
            bagian = mod.replace("ragcore.", "").split(".")[0]
            if bagian in atas:
                pelanggar.append(f"{p.name} -> {mod}")
    assert not pelanggar, (
        f"domain/ mengimpor lapisan di atasnya - arah ketergantungan terbalik: "
        f"{pelanggar}")


# --------------------------------------------------------------------------
# 17. ui/ adalah lapisan presentasi (paling atas). Tidak ada lapisan di
#     bawahnya yang boleh mengimpornya - kalau generation atau retrieval
#     mulai bergantung pada ui, logika inti terikat pada Streamlit dan tidak
#     bisa diuji maupun dipakai ulang tanpa antarmuka web.
# --------------------------------------------------------------------------
def test_inti_tidak_bergantung_ke_ui():
    pelanggar = []
    for p in _modul_python():
        if "ui" in p.parts[:-1] or p.parent.name == "ui":
            continue        # ui/ sendiri boleh apa saja ke bawah
        t = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(t):
            mod = n.module if isinstance(n, ast.ImportFrom) else (
                n.names[0].name if isinstance(n, ast.Import) else None)
            if not mod:
                continue
            # cocokkan komponen paket 'ui' secara utuh, bukan substring
            bagian = mod.replace("ragcore.", "").split(".")
            if bagian and bagian[0] == "ui":
                pelanggar.append(f"{p.name} -> {mod}")
    assert not pelanggar, (
        f"lapisan inti mengimpor ui/ (presentasi) - arah terbalik: {pelanggar}")


# --------------------------------------------------------------------------
# 18. Nama argumen di docstring tool HARUS cocok dengan parameter fungsinya.
#     docstring tool menjadi deskripsi yang DILIHAT model; kalau ia menyebut
#     arg 'pertanyaan' sementara skema memakai 'question', model memanggil
#     tool dengan kwarg yang salah, ditolak, lalu membuang giliran untuk retry.
#     PERNAH TERJADI: refactor pengenal mengganti param tapi bukan docstring.
# --------------------------------------------------------------------------
def test_docstring_arg_tool_cocok_dengan_skema():
    import re

    from ragcore.agent.tools import count, search_policy
    from ragcore.agent.tools_hybrid import search_rules

    salah = []
    for tool in (search_rules, search_policy, count):
        skema = set(tool.args)
        # baris "    nama:" di bagian Args docstring
        disebut = re.findall(r"^\s{4,}(\w+):", tool.description, re.M)
        for nama in disebut:
            # hanya periksa yang tampak seperti nama argумen (bukan kalimat)
            if nama.islower() and nama not in skema and len(nama) > 2:
                salah.append(f"{tool.name}: docstring menyebut '{nama}', "
                             f"skema {sorted(skema)}")
    assert not salah, (
        "nama argumen di docstring tool tidak cocok skema - model akan "
        "memanggil dengan kwarg salah:\n  " + "\n  ".join(salah))


# --------------------------------------------------------------------------
# 19. Kwarg di setiap pemanggilan answer() harus cocok dengan signature-nya.
#     PERNAH TERJADI: ui12 memanggil answer(users=...) padahal parameternya
#     app_user - TypeError yang menyala begitu pengguna login bertanya, tapi
#     tak ada tes yang menjalankan Streamlit, jadi lolos ke produksi.
# --------------------------------------------------------------------------
def test_pemanggil_answer_memakai_kwarg_sah():
    import inspect

    from ragcore.generation.answerer import answer

    sah = set(inspect.signature(answer).parameters)
    pelanggar = []
    for p in _modul_python():
        t = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(t):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "answer"):
                for kw in n.keywords:
                    if kw.arg is not None and kw.arg not in sah:
                        pelanggar.append(f"{p.name}:{n.lineno} answer({kw.arg}=...)")
    assert not pelanggar, (
        "answer() dipanggil dengan kwarg yang bukan parameternya - TypeError "
        "saat jalur itu dieksekusi:\n  " + "\n  ".join(pelanggar)
        + f"\n  parameter sah: {sorted(sah)}")


# --------------------------------------------------------------------------
# 20. Tier publik HARUS memakai sambungan non-pemilik. PUBLIC yang keliru
#     dipetakan ke sambungan pemilik akan membuat "tanpa login" melihat SEMUA
#     dokumen - kebalikan dari yang dimaksud. Ini menjaga pemisahan itu.
# --------------------------------------------------------------------------
def test_public_bukan_sambungan_pemilik():
    from ragcore import config
    from ragcore.domain.users import PUBLIC, connection_for

    pub = connection_for(PUBLIC)
    assert pub != config.PG_URL, "PUBLIC tidak boleh memakai sambungan pemilik"
    assert "rag_app" in pub, "PUBLIC harus lewat peran aplikasi non-pemilik"
    assert "options" not in pub, "PUBLIC tidak boleh membawa unit"
    # None tetap pemilik (jalur maintenance) - kontras yang harus dijaga
    assert connection_for(None) == config.PG_URL
