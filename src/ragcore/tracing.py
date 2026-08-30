"""Pengiriman tracing ke Langfuse, dengan jalur mati yang aman (L12).

Kalau kunci tidak diisi, seluruh fungsi di sini menjadi tanpa efek dan
sistem tetap berjalan normal. Itu bukan kemudahan, melainkan syarat:
observability TIDAK BOLEH menjadi prasyarat agar aplikasi bisa hidup.
Sistem yang mati karena server jejaknya mati sudah menukar satu masalah
dengan masalah yang lebih besar.

Kenapa Langfuse dan bukan LangSmith: LangSmith tidak bisa self-hosted
tanpa lisensi Enterprise. Untuk organisasi yang memilih on-premise justru
karena datanya tidak boleh keluar, mengirim tracing - yang memuat pertanyaan
users dan chunks dokumen - ke layanan terkelola membatalkan seluruh
alasan memilih on-premise sejak awal.
"""
from __future__ import annotations

import os

from ragcore import config
from ragcore.log import get_logger

log = get_logger(__name__)

# False berarti "sudah dicoba dan gagal" - dibedakan dari None yang berarti
# "belum pernah dicoba". Tanpa pembedaan itu, setiap pemanggilan akan
# mencoba menyambung ulang dan mencetak errors yang sama berulang kali.
_handler: object | None = None


def callback_handler():
    """Callback handler LangChain, atau None bila tracing dimatikan.

    DUA TATA CARA, KARENA API-NYA BERUBAH ANTARVERSI:

      langfuse 3.x : CallbackHandler(public_key=, secret_key=, host=)
      langfuse 4.x : CallbackHandler(public_key=) saja — kredensial dan host
                     diambil dari klien Langfuse yang sudah disiapkan lebih
                     dulu, atau dari variabel lingkungan.

    Diuji pada 4.14.5: memberi `secret_key` dan `host` melempar TypeError,
    dan karena seluruh modul ini dirancang gagal dengan aman, jejaknya
    "dimatikan" tanpa satu pun petunjuk bahwa sebabnya sekadar tanda tangan
    fungsi yang berubah. Aman memang benar — tetapi diam tidak.

    Karena itu galatnya kini disebutkan lengkap, dan kedua tata cara dicoba.
    """
    global _handler

    if not config.USE_TRACING:
        return None
    if _handler is not None:
        return _handler or None

    # KUNCI TANPA HOST = TRACE LARI KE CLOUD, DIAM-DIAM.
    #
    # Pada 4.x, CallbackHandler mengambil klien global lewat get_client(), yang
    # membaca LANGFUSE_HOST dari ENVIRONMENT - bukan dari argumen Langfuse(...)
    # di bawah. Kalau seseorang menyetel hanya PUBLIC/SECRET_KEY (lewat env
    # atau .env) tanpa LANGFUSE_HOST, SDK diam-diam memakai https://cloud.langfuse.com,
    # dan trace ke Langfuse lokal tidak pernah sampai - tanpa satu pun galat.
    # Terbukti live: OTLP POST 200, tetapi ke host yang salah.
    #
    # Karena itu host dipastikan ada di env sebelum handler dibuat. config
    # selalu punya nilainya (bawaan http://localhost:3000), jadi ini menutup
    # celah "lupa mengisi LANGFUSE_HOST" untuk selamanya.
    os.environ.setdefault("LANGFUSE_HOST", config.LANGFUSE_HOST)

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        # Menyiapkan klien lebih dulu: pada 4.x inilah yang memegang
        # kredensial dan host, dan CallbackHandler menemukannya dari sana.
        Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
        try:
            _handler = CallbackHandler(
                public_key=config.LANGFUSE_PUBLIC_KEY)          # 4.x
        except TypeError:
            _handler = CallbackHandler(                        # 3.x
                public_key=config.LANGFUSE_PUBLIC_KEY,
                secret_key=config.LANGFUSE_SECRET_KEY,
                host=config.LANGFUSE_HOST,
            )
    except Exception as e:
        log.warning("Jejak dimatikan (%s: %s). Sistem tetap berjalan.",
                    type(e).__name__, e)
        _handler = False
    return _handler or None


# Kunci metadata yang DIANGKAT Langfuse menjadi atribut tracing. Selain yang
# ada di daftar ini, apa pun berawalan "langfuse_" hanya menjadi metadata
# biasa - diam-diam, tanpa errors.
VALID_TRACE_KEYS = frozenset({
    "langfuse_user_id",
    "langfuse_session_id",
    "langfuse_tags",
    "langfuse_trace_name",
    "langfuse_prompt",
})


def check_trace_keys(metadata: dict) -> list[str]:
    """Peringatkan kunci berawalan langfuse_ yang salah ketik.

    KENAPA PENJAGA INI ADA. Langfuse mengangkat beberapa kunci metadata
    menjadi atribut tracing: user_id, session_id, tag. Yang TIDAK dikenalnya
    tidak ditolak - ia hanya disimpan sebagai metadata biasa.

    Akibatnya satu huruf yang salah:

        langfuse_session_id   -> halaman Sessions terisi
        langfuse_sessionid    -> halaman Sessions KOSONG, tanpa satu pun errors

    Dan halaman yang kosong terbaca sebagai "fiturnya belum dipakai", bukan
    sebagai "ada yang salah ketik". Itu bentuk kegagalan yang paling mahal:
    tidak ada yang rusak, hanya sesuatu yang tidak pernah muncul.

    Penjaga ini tidak bisa menangkap semua kesalahan - kunci yang benar tapi
    nilainya keliru tetap lolos. Yang ia tangkap adalah kesalahan yang paling
    sering terjadi dan paling lama terdeteksi.
    """
    mencurigakan = [k for k in metadata
                    if k.startswith("langfuse_") and k not in VALID_TRACE_KEYS]
    for k in mencurigakan:
        dekat = [s for s in VALID_TRACE_KEYS
                 if s.replace("_", "") == k.replace("_", "").lower()]
        saran = f" Maksud Anda '{dekat[0]}'?" if dekat else ""
        log.warning("Kunci trace '%s' tidak dikenal Langfuse dan akan menjadi "
                    "metadata biasa.%s", k, saran)
    return mencurigakan


def trace_identity(person) -> str | None:
    """Penanda users untuk server tracing. NIP, bukan nama.

    PILIHAN YANG DISENGAJA. Langfuse memakai user_id untuk menjawab
    pertanyaan operasional yang sah: siapa yang memakai sistem ini, siapa
    yang paling sering ditolak, apakah satu unit mengalami mutu jawaban
    yang lebih buruk. Semua itu butuh penanda yang STABIL, bukan nama.

    NIP sudah cukup untuk menjawab semuanya, dan lebih mudah dicabut
    hubungannya dengan orang bila jejaknya kelak dibagikan atau diarsipkan.
    Nama tidak menambah satu pun kemampuan diagnosis.
    """
    if person is None:
        return None
    return getattr(person, "nip", None) or str(person)


def invoke_config(nama_alur: str = "tanya-sop", person=None,
                       session: str | None = None, tag: list[str] | None = None,
                       **metadata) -> dict:
    """Susun argumen config untuk .invoke(). Aman dipakai meski tracing mati.

    Pemakaiannya di sisi pemanggil hanya satu argumen tambahan:

        llm.invoke(prompt, config=invoke_config(
            "jawab-sop", orang=users, sesi=id_percakapan))

    PENGGUNA DAN SESI ADALAH DUA SUMBU YANG BERBEDA, dan Langfuse memang
    memisahkannya:

      user_id     menjawab "siapa yang memakai sistem ini"
      session_id  menjawab "apa yang terjadi sepanjang SATU percakapan"

    Yang kedua itulah yang membuat tracing bisa dibaca sebagai cerita, bukan
    sebagai daftar panggilan lepas. Pertanyaan lanjutan yang meleset hampir
    selalu masuk akal begitu giliran sebelumnya ikut terlihat - dan tanpa
    session_id, keduanya tidak pernah berdampingan di layar.

    Sumbernya sudah ada di lab ini, tinggal disambungkan:
      - users dari login (lihat users.py, materi RBAC L6)
      - sesi dari thread_id LangGraph (L10) atau sesi ui web

    PRIVASI. Apa pun yang masuk metadata tersimpan di server tracing dan
    terbaca siapa pun yang punya akses ke sana. Yang dikirim di sini: NIP
    (bukan nama), unit, peran, jumlah dan nama berkas sumber. Yang TIDAK
    pernah dikirim: isi dokumen. Tetapkan kebijakan storage tracing -
    30 sampai 90 hari umumnya cukup untuk diagnosis - SEBELUM menyalakannya,
    bukan setelah datanya menumpuk.
    """
    handler = callback_handler()
    if handler is None:
        return {}

    if person is not None:
        metadata.setdefault("unit", getattr(person, "unit", None))
        metadata.setdefault("peran", getattr(person, "peran", None))

    # Kunci berawalan langfuse_ TIDAK menjadi metadata biasa - ia diangkat
    # menjadi atribut tracing (user, session, tag). Salah ketik di sini tidak
    # memunculkan errors; nilainya hanya diam-diam menjadi metadata biasa.
    nip = trace_identity(person)
    if nip:
        metadata["langfuse_user_id"] = nip
    if session:
        metadata["langfuse_session_id"] = str(session)
    if tag:
        metadata["langfuse_tags"] = list(tag)

    check_trace_keys(metadata)

    return {
        "callbacks": [handler],
        "run_name": nama_alur,
        "metadata": {k: v for k, v in metadata.items() if v is not None},
    }


def flush() -> None:
    """Paksa kirim jejak yang masih tertunda. Aman dipanggil meski tracing mati.

    KENAPA PERLU DI JALUR LATAR. Ekspor OTLP 4.x mengirim jejak secara BATCH,
    dijadwalkan beberapa detik sekali. Untuk permintaan web biasa itu tidak
    terasa - sesi tetap hidup dan batch berikutnya keburu terkirim. Tapi
    pekerja ingest berjalan di thread latar dan bisa menuntaskan satu dokumen
    lalu diam; tanpa flush, jejak halaman terakhir menunggu batch yang mungkin
    lama datang. Memanggil ini di akhir tiap tugas membuat jejaknya muncul di
    Langfuse mendekati real time, bukan menyusul belakangan.
    """
    if not config.USE_TRACING:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:
        log.debug("flush jejak dilewati (%s: %s)", type(e).__name__, e)


def _client():
    """Klien Langfuse mentah untuk penilaian. None bila tracing dimatikan."""
    if not config.USE_TRACING:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
    except Exception:
        return None


def score(id_tracing: str, name: str, value: float,
              note: str | None = None) -> bool:
    """Lampirkan skor ke satu tracing. Kembalikan False bila tidak terkirim.

    Skor yang paling berguna justru yang OTOMATIS, dihitung dari pemeriksaan
    yang sudah ada: cakupan citation, apakah sistem menolak, mutu ekstraksi
    sumbernya. Penilaian manusia berguna, tapi datangnya jarang dan
    condong - orang melapor saat jawabannya salah, bukan saat benar.
    """
    lf = _client()
    if lf is None:
        return False
    try:
        lf.create_score(trace_id=id_tracing, name=name, value=value,
                        comment=note)
        return True
    except Exception:
        return False


def auto_score(id_tracing: str, answer_text: str, coverage: float,
                  chunks: list | None = None) -> None:
    """Kirim skor yang bisa dihitung tanpa manusia. Dipanggil tiap jawaban."""
    score(id_tracing, "cakupan_sitasi", coverage)
    score(id_tracing, "menolak",
              1.0 if config.NOT_FOUND in (answer_text or "") else 0.0)

    if chunks:
        not_yet = sum(d.metadata.get("mutu_ekstraksi") == "perlu_tinjau"
                    for d in chunks)
        score(id_tracing, "sumber_belum_terverifikasi", float(not_yet))
