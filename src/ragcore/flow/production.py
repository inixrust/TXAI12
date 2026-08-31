"""LangGraph untuk alur produksi (L10).

Tiga hal yang tidak ada di graf TX-AI11, dan ketiganya berasal dari satu
perubahan: keadaan disimpan di Postgres, bukan di memori.

  1. Pemulihan setelah mati. Jalankan ulang dengan thread_id yang sama,
     alur melanjutkan dari simpul terakhir yang selesai.
  2. Jeda untuk persetujuan manusia. Alur berhenti, keadaannya tersimpan,
     proses boleh mati, peninjau boleh datang besok.
  3. Ingatan antar-giliran. Pertanyaan lanjutan seperti "kalau untuk yang
     alih status?" bisa dipahami karena riwayatnya ada.

Checkpointer memakai basis data yang SAMA dengan indeks pgvector - satu
Postgres, dua kegunaan. Itu disengaja: satu lagi hal yang tidak perlu
dicadangkan dan dipantau secara terpisah.
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from ragcore import config

# NOT_FOUND diimpor terpisah karena beberapa simpul punya parameter bernama
# `config` (wajib demikian agar LangGraph mengisinya) yang menaungi modul config.
from ragcore.config import NOT_FOUND
from ragcore.generation.answerer import compose_answer
from ragcore.generation.citation import check_citation
from ragcore.model import get_llm
from ragcore.retrieval.retriever import retrieve_best


class State(TypedDict, total=False):
    """Yang dibawa antar-simpul. Semua opsional supaya graf bisa dimasuki
    dari beberapa titik saat melanjutkan setelah mati."""
    question: str
    nip: str                   # identitas pemohon untuk RLS di simpul retrieval
    self_question: str
    history: Annotated[list, lambda a, b: (a or []) + (b or [])]
    chunks: list
    answer_text: str
    coverage: float
    status: str
    note: str
    judgment: bool             # pertanyaan menuntut VONIS kepatuhan, bukan fakta
    force_review: bool         # jalur uji: paksa tinjauan tanpa pemicu nyata


# ---------------------------------------------------------- checkpointer

def open_checkpointer():
    """Context manager PostgresSaver. Panggil .setup() sekali di awal.

    Perhatikan bentuk URL-nya: PostgresSaver memakai psycopg langsung,
    jadi ia butuh 'postgresql://', BUKAN 'postgresql+psycopg://' yang
    dipakai SQLAlchemy di sisi pgvector. Dua pustaka, dua tata tulis,
    satu basis data - dan galatnya kalau tertukar tidak menyebut itu.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    return PostgresSaver.from_conn_string(config.PG_URL_DIRECT)


def run_flow(inputs, thread_id: str):
    """Jalankan/lanjutkan graf pada thread_id, kembalikan state akhir.

    Checkpointer dibuka BARU tiap aksi, bukan disimpan di memori: itu justru
    yang membuktikan keadaan hidup di Postgres, bukan di proses. Aksi apa pun -
    pertanyaan baru ATAU melanjutkan (Command(resume=...)) setelah tinjauan -
    memakai thread_id yang sama dan memungut keadaannya dari basis data.

    Dipakai UI (mengajukan) DAN application/review_service (melanjutkan setelah
    keputusan peninjau) - satu jalur, supaya penegakan keputusan hanya punya
    SATU titik masuk ke graf.
    """
    with open_checkpointer() as cp:
        cp.setup()
        graph = build_graph(checkpointer=cp)
        return graph.invoke(
            inputs, config={"configurable": {"thread_id": thread_id}})


# ----------------------------------------------------------------- simpul

def _requester(state: State):
    """User pemohon dari NIP di state - untuk RLS retrieval DAN atribusi jejak.

    FAIL-CLOSED untuk NIP TAK DIKENAL. NIP kosong = konteks operator -> None
    (sambungan pemilik, seperti connection_for(None)). Tapi NIP yang TERISI
    namun tak ada di REGISTRY (mis. identitas basi/typo) TIDAK boleh jatuh ke
    None - itu memberi akses pemilik yang kebal RLS (fail-open). Ia
    diperlakukan sebagai PUBLIC: umum saja.
    """
    from ragcore.domain import users as P
    nip = (state.get("nip") or "").strip()
    if not nip:
        return None                      # operator/maintenance, tanpa identitas
    return P.REGISTRY.get(nip) or P.PUBLIC   # NIP asing -> umum, BUKAN pemilik


def _session_of(run_config: dict | None) -> str | None:
    """thread_id LangGraph = session_id Langfuse: satu percakapan, satu id."""
    return (run_config or {}).get("configurable", {}).get("thread_id")


def n_rewrite(state: State, config: dict | None = None) -> dict:
    """Jadikan pertanyaan mandiri dengan bantuan riwayat (B5, kini berkeadaan).

    Parameter kedua WAJIB bernama `config`: hanya nama itu yang diisi LangGraph
    dengan RunnableConfig (termasuk thread_id). `run_config` atau anotasi lain
    diam-diam tetap None - itu sebabnya session_id graf dulu selalu kosong.

    Riwayat DIBATASI. Percakapan yang panjang bukan hanya mahal - ia juga
    menurunkan mutu, karena giliran lama yang tidak relevan ikut membentuk
    penulisan ulang. Enam giliran terakhir sudah lebih dari cukup.
    """
    history = (state.get("history") or [])[-6:]
    if not history:
        return {"self_question": state["question"]}


    # Bentuk giliran bisa berbeda saat alur dilanjutkan dari keadaan lama;
    # .get + saring dict mencegah satu entri asing menjatuhkan simpul pertama.
    conversation = "\n".join(f"{p.get('peran', '?')}: {p.get('isi', '')}"
                             for p in history if isinstance(p, dict))
    prompt = (
        f"Riwayat percakapan:\n{conversation}\n\n"
        f"Pertanyaan lanjutan: {state['question']}\n\n"
        f"Tulis ulang pertanyaan lanjutan itu menjadi pertanyaan yang berdiri "
        f"sendiri, tanpa perlu membaca riwayat. Keluarkan HANYA pertanyaannya."
    )
    # Jejak Langfuse: penulisan-ulang JUGA pemanggilan LLM. Tanpa config ini ia
    # tak terlihat di observability - kelas gap yang sama dengan ekstraksi VLM.
    from ..tracing import invoke_config
    jejak = invoke_config("tulis-ulang-pertanyaan", person=_requester(state),
                          session=_session_of(config),
                          tag=["konsultasi", "tulis-ulang"])
    return {"self_question": get_llm().invoke(prompt, config=jejak).content.strip()}


def n_classify(state: State) -> dict:
    """Tentukan apakah ini pertanyaan PENILAIAN, bukan sekadar fakta.

    Bedanya menentukan kasus nyata di hilir. "Berapa lama masa percobaan?"
    adalah PENCARIAN FAKTA - jawabannya ada hitam di atas putih, aman dijawab
    otomatis. "Apakah saya boleh mengambil cuti 20 hari sekaligus?" adalah
    permintaan VONIS KEPATUHAN atas situasi spesifik seseorang - dan vonis
    semacam itu, bila salah, berkonsekuensi (HR, hukum, hubungan kerja).
    Karena itu ia ditahan untuk disetujui peninjau; lihat needs_review().

    Deteksinya masih berbasis kata kunci (cukup untuk PoC); router berbasis
    LLM adalah langkah berikutnya bila pola pertanyaan makin beragam.

    CATATAN SUMBER DATA. Simpul ini dulu juga "memilih sumber" (dokumen vs
    basis data), tapi cabang basis-datanya tak pernah tersambung - hanya stub.
    Menjawab dari DATA orang/transaksi (v_karyawan, v_cuti, ...) sudah menjadi
    tugas AGENT hibrida L9 yang punya alat SQL sendiri; menaruh text-to-SQL di
    sini akan menduplikasinya DAN tak ter-scope per orang. Maka graf ini jujur
    mengerjakan satu hal: konsultasi dari DOKUMEN dengan tinjauan manusia.
    """
    t = (state.get("self_question") or state["question"]).lower()
    # Penanda dipilih agar TAHAN sisipan subjek: "apakah boleh" tak akan cocok
    # dengan "apakah SAYA boleh" - itu pernah lolos diam-diam. Maka dipakai
    # akar kata izin/kepatuhan sebagai substring: "boleh" menangkap boleh,
    # bolehkah, diperbolehkan; dst. Cukup untuk PoC; router LLM langkah lanjut.
    JUDGMENT_MARKERS = ("boleh", "melanggar", "diizinkan", "berhak",
                        "memenuhi syarat", "sanksi", "pelanggaran")
    return {"judgment": any(m in t for m in JUDGMENT_MARKERS)}


def n_search_documents(state: State) -> dict:
    """Ambil chunks - DENGAN kontrol akses pemohon.

    KEAMANAN, DAN INI BUKAN OPSIONAL. retrieve_best TANPA person memakai
    sambungan PEMILIK tabel yang KEBAL RLS - benar untuk indexing/operator,
    tapi bocor total bila dipakai melayani pertanyaan user: satu staf bisa
    membaca dokumen terbatas unit lain. State membawa NIP pemohon; di sini ia
    menjadi identitas RLS (sambungan) DAN filter aplikasi - sama persis dengan
    jalur answer(). NIP kosong (dijalankan operator/uji) jatuh ke None =
    pemilik, sesuai konvensi connection_for(None) di seluruh sistem.
    """
    from ragcore.retrieval.filters import filter_for

    person = _requester(state)
    return {"chunks": retrieve_best(
        state.get("self_question") or state["question"],
        filters=filter_for(person), person=person)}


def n_compose_answer(state: State, config: dict | None = None) -> dict:
    """Susun jawaban dari chunks yang sudah diambil.

    Sengaja memakai compose_answer() yang sederhana, BUKAN jawab() yang
    lengkap: jawab() ikut melakukan retrieval sendiri, dan di dalam graf
    retrieval sudah dikerjakan simpul tersendiri. Memanggilnya di sini
    berarti korpus dicari dua kali per pertanyaan.
    """

    chunks = state.get("chunks") or []
    if not chunks:
        # NOT_FOUND diimpor langsung: di sini `config` adalah parameter
        # RunnableConfig, bukan modul config (lihat catatan di n_rewrite).
        return {"answer_text": NOT_FOUND, "coverage": 0.0}

    question = state.get("self_question") or state["question"]

    # thread_id LangGraph DAN session_id Langfuse adalah gagasan yang sama:
    # satu percakapan yang berlanjut. Memakai nilai yang sama untuk keduanya
    # membuat tracing di Langfuse bisa ditelusuri balik ke keadaan yang
    # tersimpan di Postgres, dan sebaliknya.
    # person diteruskan supaya jejak jawaban di Langfuse teratribusi ke NIP
    # pemohon (bukan anonim) - siapa yang bertanya ikut terekam untuk audit.
    return {"answer_text": compose_answer(
        get_llm(), question, chunks,
        person=_requester(state), session=_session_of(config))}


def n_check_citation(state: State) -> dict:
    """Hitung cakupan citation — dasar keputusan peninjauan manusia."""

    report = check_citation(state.get("answer_text") or "",
                             len(state.get("chunks") or []))
    return {"coverage": report.coverage}


def needs_review(state: State) -> str:
    """Aturan DETERMINISTIK, ditulis Anda - bukan diputuskan model.

    Kalau model yang memutuskan kapan ia perlu diperiksa manusia, maka
    jawaban yang paling percaya diri justru yang paling jarang diperiksa.
    """
    if state.get("answer_text") == config.NOT_FOUND:
        return "lolos"          # menolak menjawab - tak ada vonis untuk ditinjau

    # KASUS NYATA #1: pertanyaan menuntut VONIS kepatuhan. AI boleh menyusun
    # draf, tapi keputusan "boleh/tidak/melanggar" atas situasi spesifik
    # seseorang tidak dirilis tanpa disetujui manusia.
    if state.get("judgment"):
        return "tinjau"

    # KASUS NYATA #2: jawaban tidak cukup kokoh. Cakupan sitasi rendah berarti
    # ada klaim yang tidak tersandar ke sumber - itu risiko halusinasi.
    if state.get("coverage", 1.0) < config.COVERAGE_THRESHOLD:
        return "tinjau"

    # KASUS NYATA #3: sumbernya halaman pindaian yang BELUM diverifikasi
    # manusia (VLM bisa salah baca). Jawaban di atasnya ditahan dulu.
    if any(d.metadata.get("mutu_ekstraksi") == "perlu_tinjau"
           for d in state.get("chunks") or []):
        return "tinjau"

    # Jalur uji: memaksa tinjauan tanpa pemicu nyata (dipakai tes HITL).
    if state.get("force_review"):
        return "tinjau"

    return "lolos"


def _hold_reason(state: State) -> str:
    """Kenapa jawaban ini ditahan - kalimat untuk peninjau, bukan kode galat.

    Urutannya mengikuti needs_review(): alasan yang paling menentukan dulu.
    """
    if state.get("judgment"):
        return ("pertanyaan menuntut vonis kepatuhan atas situasi spesifik - "
                "keputusan wajib disetujui manusia sebelum dirilis")
    if state.get("coverage", 1.0) < config.COVERAGE_THRESHOLD:
        return "cakupan sitasi di bawah ambang - jawaban mungkin tak sepenuhnya tersandar sumber"
    if any(d.metadata.get("mutu_ekstraksi") == "perlu_tinjau"
           for d in state.get("chunks") or []):
        return "sumbernya halaman pindaian yang belum diverifikasi manusia"
    return "ditandai untuk tinjauan (mode uji)"


def n_review(state: State) -> dict:
    """Berhenti, tunggu peninjau.

    Keadaan tersimpan di Postgres selama menunggu. Yang ditampilkan ke
    peninjau harus cukup untuk MENILAI, bukan sekadar memberi tahu:
    pertanyaannya, jawabannya, sumbernya, dan alasan kenapa ia ditahan.
    Peninjau yang hanya melihat jawaban akan menyetujui semuanya.
    """
    from langgraph.types import interrupt

    decision = interrupt({
        "request": "Setujui jawaban ini dikirim ke pemohon?",
        "question": state.get("self_question") or state.get("question"),
        "answer_text": state.get("answer_text"),
        "source": [d.metadata.get("source") for d in state.get("chunks") or []],
        "citation_coverage": state.get("coverage", 0),
        "hold_reason": _hold_reason(state),
    })

    action = (decision or {}).get("action")
    if action == "approve":
        return {"status": "approved"}
    if action == "revise":
        return {"status": "revised", "note": (decision or {}).get("note", "")}
    return {"status": "rejected", "answer_text": "Dibatalkan oleh peninjau."}


# ------------------------------------------------------------------- graf

def build_graph(checkpointer=None):
    """Susun dan kompilasi graf. checkpointer=None -> tanpa keadaan."""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(State)
    g.add_node("tulis_ulang", n_rewrite)
    g.add_node("klasifikasi", n_classify)
    g.add_node("cari_dokumen", n_search_documents)
    g.add_node("susun", n_compose_answer)
    g.add_node("periksa", n_check_citation)
    g.add_node("tinjau", n_review)

    g.add_edge(START, "tulis_ulang")
    g.add_edge("tulis_ulang", "klasifikasi")
    g.add_edge("klasifikasi", "cari_dokumen")
    g.add_edge("cari_dokumen", "susun")
    g.add_edge("susun", "periksa")

    # Hanya jawaban berisiko yang ditinjau manusia - bukan semuanya.
    # Peninjauan yang terlalu sering diminta akan berhenti dibaca.
    g.add_conditional_edges("periksa", needs_review, {
        "tinjau": "tinjau",
        "lolos": END,
    })
    g.add_edge("tinjau", END)

    return g.compile(checkpointer=checkpointer)
