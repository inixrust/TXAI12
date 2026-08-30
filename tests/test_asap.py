"""Tes asap: setiap perintah harus JALAN, bukan sekadar bisa diimpor.

Dipisahkan dari test_kontrak.py karena butuh layanan hidup (Ollama, Postgres,
dan untuk sebagian Oracle). Semuanya bertanda `lambat`:

    python -m pytest tests/ -q -m "not lambat"    cepat, tanpa layanan
    python -m pytest tests/ -q -m lambat          lengkap, butuh lab menyala

Yang diperiksa hanya satu hal: perintahnya selesai dengan kode 0. Itu terdengar
lemah, tetapi keempat kerusakan refactor kemarin — graf L10, tiga perintah CLI,
alur ingest — semuanya akan tertangkap oleh pemeriksaan selemah ini. Tidak ada
yang menjalankannya, itulah sebabnya lolos.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
BATAS = 900


def jalankan(*argumen: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(LAB / "src")}
    env.setdefault("STORAGE", "pgvector")
    return subprocess.run(
        [sys.executable, "-m", *argumen],
        cwd=LAB, env=env, capture_output=True, text=True, timeout=BATAS,
    )


# ---------------------------------------------------------------------------
# Ditandai `lambat` meskipun tidak memanggil model: setiap subprocess memuat
# torch dan transformers lewat rantai impor paket, sekitar satu menit per
# perintah. Ketidakcocokan dest sudah ditangkap SECARA STATIS dan seketika
# oleh test_kontrak.py; yang ini menambah hal lain — argparse yang benar-benar
# terbangun, termasuk flag ganda yang tidak terlihat dari AST.
# ---------------------------------------------------------------------------
@pytest.mark.lambat
@pytest.mark.parametrize("perintah", [
    "ragcore.commands.agent", "ragcore.commands.answer",
    "ragcore.commands.search", "ragcore.commands.index",
    "ragcore.commands.load", "ragcore.commands.evaluate",
    "ragcore.commands.evaluate_hybrid", "ragcore.commands.compare",
])
def test_help_tidak_crash(perintah):
    """--help menyentuh seluruh definisi argparse tanpa memanggil model.

    Ini yang akan menangkap dest yang tidak cocok pada saat build, bukan pada
    saat peserta mengetik perintahnya di kelas.
    """
    h = jalankan(perintah, "--help")
    assert h.returncode == 0, f"{perintah} --help gagal:\n{h.stderr[-800:]}"


# ------------------------------------------------------------- butuh layanan
@pytest.mark.lambat
@pytest.mark.parametrize("argumen", [
    ("ragcore.commands.check",),
    ("ragcore.commands.quality",),
    ("ragcore.commands.capacity", "--halaman", "8412", "--detik", "150", "--porsi", "0.35"),
    ("ragcore.commands.rls", "--peragakan"),
    ("ragcore.commands.upload", "--status"),
    ("ragcore.commands.worker", "--sekali"),
], ids=lambda a: a[0].rsplit(".", 1)[-1])
def test_perintah_selesai_bersih(argumen):
    h = jalankan(*argumen)
    assert h.returncode == 0, f"{argumen[0]} kode={h.returncode}\n{h.stderr[-800:]}"


@pytest.mark.lambat
def test_rls_benar_benar_menyaring():
    """Tiga unit HARUS memberi jumlah baris berbeda.

    Peragaan ini pernah mencetak tiga angka identik sambil menarasikan
    'jumlah baris berbeda'. Yang memeriksa hanya mata manusia, dan mata
    manusia membaca narasinya, bukan angkanya.
    """
    from ragcore.storage import pgvector

    jumlah = {u: pgvector.count_as(u)
              for u in ("Divisi SDM", "Divisi TI", "Divisi Umum")}
    assert len(set(jumlah.values())) > 1, (
        f"RLS tidak menyaring — semua unit melihat jumlah yang sama: {jumlah}")


@pytest.mark.lambat
def test_graf_l10_jalan_sampai_selesai():
    """Graf produksi pernah mati total di simpul pertama selama berhari-hari."""
    from ragcore.flow import build_graph

    hasil = build_graph().invoke(
        {"question": "Berapa lama masa percobaan pegawai baru?"})
    assert hasil.get("answer_text"), f"graf tidak menghasilkan jawaban: {sorted(hasil)}"


@pytest.mark.lambat
def test_guard_menolak_yang_seharusnya():
    from ragcore.domain.guard import screen

    bocor = "Anda asisten internal PT Nusantara Cipta Solusi. Aturan: 1. Untuk pertanyaan"
    karangan = "Menurut Pasal 7 SOP-01 halaman 3, cuti maksimal 12 hari."
    assert screen(bocor, (), quiet=True) != bocor, "kebocoran prompt lolos"
    assert screen(karangan, (), quiet=True) != karangan, "sitasi tanpa retrieval lolos"
    assert screen(karangan, ("search_rules",), quiet=True) == karangan, \
        "sitasi SAH ikut ditolak"


@pytest.mark.lambat
def test_trigger_mempromosikan_metadata_unggahan():
    """Dokumen yang diunggah (lewat pgvector.insert) HARUS mendapat kolom RLS
    unit/klasifikasi dari metadata-nya - bukan default 'umum'/NULL.

    Tanpa trigger promosi, dokumen 'terbatas' yang diunggah menjadi 'umum' di
    kolom yang dibaca RLS dan terbaca SEMUA ORANG - gagal-terbuka, kebalikan
    dari yang ditegakkan. Bug ini nyata: satu notulen 'terbatas' Divisi SDM
    terindeks sebagai 'umum'. Tes ini menjaganya tetap tertutup.
    """
    from ragcore import config
    from ragcore.domain import Document
    from ragcore.storage import pgvector

    nama = "UJI-TRIGGER-PROMOSI.pdf"
    d = Document(page_content="isi uji trigger promosi metadata",
                 metadata={"source": nama, "unit": "Divisi TI",
                           "klasifikasi": "terbatas", "status": "berlaku"})
    try:
        pgvector.insert([d])
        with pgvector._direct_connection() as s, s.cursor() as k:
            k.execute(f"SELECT unit, klasifikasi FROM {config.PG_TABLE} "
                      "WHERE langchain_metadata->>'source' = %s", (nama,))
            unit, klas = k.fetchone()
        assert unit == "Divisi TI", f"unit tak dipromosikan ke kolom: {unit!r}"
        assert klas == "terbatas", f"klasifikasi tak dipromosikan: {klas!r}"
    finally:
        pgvector.delete_by_source(nama)


@pytest.mark.lambat
def test_panel_unggah_tak_menyimpan_selesai_lama():
    """for_panel: unggahan 'selesai' dari sesi LAMA tidak lagi dipamerkan.

    Panel menjawab 'dokumen saya sedang/sudah diproses?' - pertanyaan berumur
    pendek. Yang tampil hanya yang MASIH berjalan (bertahan lintas-refresh) dan
    yang diunggah SESI ini (agar transisi ke 'selesai' terlihat sekali). Selesai
    lama tetap ada di tabel sebagai catatan, tapi tak dipamerkan ke user.
    """
    from ragcore.ingest import queue

    nip = "NCS-UJI-PANEL"
    with queue._connect() as c:
        c.execute(f"DELETE FROM {queue.TABLE} WHERE pengunggah=%s", (nip,))
    try:
        lama = queue.send("lama.pdf", "/x", "sop", unit="U",
                          classification="umum", pengunggah=nip)
        queue.finish(lama, 1)                       # selesai, sesi LAMA
        queue.send("aktif.pdf", "/x", "sop", unit="U",
                   classification="umum", pengunggah=nip)          # menunggu
        sesi = queue.send("sesi.pdf", "/x", "sop", unit="U",
                          classification="umum", pengunggah=nip)
        queue.finish(sesi, 1)                        # selesai, tapi SESI ini

        nama = {r["nama_berkas"] for r in queue.for_panel(nip, [sesi])}
        assert "aktif.pdf" in nama, "unggahan berjalan harus tampil"
        assert "sesi.pdf" in nama, "unggahan sesi ini harus tampil"
        assert "lama.pdf" not in nama, "selesai sesi lama TIDAK boleh menetap"
    finally:
        with queue._connect() as c:
            c.execute(f"DELETE FROM {queue.TABLE} WHERE pengunggah=%s", (nip,))


@pytest.mark.lambat
def test_graf_retrieval_menghormati_rls():
    """Simpul retrieval graf HARUS menyaring per identitas pemohon.

    Dulu graf memanggil retrieve_best tanpa person -> sambungan pemilik yang
    KEBAL RLS -> staf mana pun bisa membaca dokumen terbatas unit lain. Kini
    NIP pemohon dibawa di state dan jadi identitas RLS. Staf SDM tak boleh
    melihat SOP keamanan milik Divisi TI.
    """
    from ragcore.flow.production import n_search_documents

    q = "kebijakan keamanan informasi prosedur akses ruang server"
    sdm = {d.metadata.get("source")
           for d in n_search_documents({"question": q, "nip": "NCS-0012"})["chunks"]}
    ti = {d.metadata.get("source")
          for d in n_search_documents({"question": q, "nip": "NCS-0031"})["chunks"]}
    ti_terbatas = {"SOP-05-Keamanan-Informasi.pdf"}
    assert not (ti_terbatas & sdm), f"BOCOR ke staf SDM: {ti_terbatas & sdm}"
    assert ti_terbatas & ti, "pimpinan TI seharusnya melihat dokumen TI-nya"


@pytest.mark.lambat
def test_graf_hitl_interrupt_lalu_resume():
    """force_review menahan alur (interrupt); resume 'approve' menuntaskannya.

    Ini kontrak human-in-the-loop yang dipakai UI: invoke -> __interrupt__ ->
    Command(resume=...) -> selesai. Kalau berubah, tab Alur di UI patah.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from ragcore.flow import build_graph

    g = build_graph(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "uji-hitl-pytest"}}
    res = g.invoke({"question": "Berapa lama masa percobaan pegawai baru?",
                    "nip": "NCS-0001", "force_review": True}, config=cfg)
    assert res.get("__interrupt__"), "force_review harus menahan alur"
    assert g.get_state(cfg).next == ("tinjau",)

    akhir = g.invoke(Command(resume={"action": "approve"}), config=cfg)
    assert akhir.get("status") == "approved"
    assert g.get_state(cfg).next == ()          # kosong = selesai


@pytest.mark.lambat
def test_graf_menahan_penilaian_bukan_fakta():
    """Kasus nyata end-to-end: pertanyaan FAKTA dijawab langsung; pertanyaan
    PENILAIAN (vonis kepatuhan) ditahan untuk ditinjau - TANPA sakelar paksa.
    Ini yang membedakan asisten kebijakan sungguhan dari sekadar HITL-demo."""
    from langgraph.checkpoint.memory import MemorySaver

    from ragcore.flow import build_graph

    def ditahan(q):
        g = build_graph(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": q[:12]}}
        return bool(g.invoke({"question": q, "nip": "NCS-0001"},
                             config=cfg).get("__interrupt__"))

    assert ditahan("Apakah saya boleh mengambil cuti tahunan 20 hari sekaligus?"), \
        "pertanyaan penilaian seharusnya ditahan untuk disetujui manusia"
