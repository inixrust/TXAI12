"""Penyimpanan vektor di PostgreSQL + pgvector (L5, L6).

Antarmukanya sengaja dibuat semirip mungkin dengan storage Chroma di
TX-AI11, sehingga sisa pipeline tidak perlu tahu yang mana sedang dipakai.
Itu pula yang membuat perbandingan recall pada Hari 2 bisa jujur: yang
berubah hanya penyimpanannya, bukan cara pengambilannya.

Alasan operasional pindah ke sini - yang paling menentukan lebih dulu:

  1. Penyaringan di kode versus PENEGAKAN di basis data. Selama pembatasan
     akses berupa `if` di aplikasi, ia berlaku hanya pada jalur yang ingat
     memanggilnya. Row-Level Security berlaku pada SETIAP query, termasuk
     query yang lupa menyaring dan termasuk psql milik orang lain.
  2. Pencadangan, replikasi, dan pemantauan sudah ada di organisasi.
  3. Satu query bisa menggabungkan kemiripan vektor dengan data relasional.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence

from ragcore import config
from ragcore.model import get_embedding


def _siapkan_event_loop_windows() -> None:
    """Windows memakai ProactorEventLoop; psycopg tidak bisa memakainya.

    PGVectorStore bekerja secara asinkron di dalam, meski ui yang kita
    pakai sinkron. Di Windows itu menabrak:

        psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'
        to run in async mode.

    Galatnya muncul saat menyambung, jauh dari sebab sesungguhnya, dan
    menyebutkan pustaka yang tidak pernah dipanggil peserta secara langsung.
    Di Linux dan macOS tidak terjadi sama sekali — jadi kalau materi disusun
    di sana, jebakan ini baru ketahuan di kelas.
    """
    if sys.platform != "win32":
        return
    policy = asyncio.get_event_loop_policy()
    if not isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_siapkan_event_loop_windows()


def _engine(url: str | None = None):
    """PGEngine dibuat baru tiap panggilan; koneksinya sendiri di-pool.

    Tidak di-cache dengan lru_cache seperti model: engine yang dipegang
    lintas proses fork (mis. Streamlit) menghasilkan errors koneksi yang
    sangat sulit dilacak.

    `url` diisi saat sambungan harus membawa identitas users — lihat
    users.connection_for(). Kosong berarti sambungan pemilik tabel.
    """
    from langchain_postgres import PGEngine

    return PGEngine.from_connection_string(url=url or config.PG_URL)


TSV_COLUMN = "content_tsv"

# 'simple' TIDAK melakukan stemming dan tidak punya daftar stopword.
#
# Bawaan pustaka adalah pg_catalog.english - dan itu SALAH untuk korpus
# berbahasa Indonesia dengan cara yang senyap: penganalisis Inggris akan
# memangkas "pengadaan" dan "penawaran" menurut aturan morfologi Inggris,
# lalu membuang kata seperti "a", "in", "is" yang di sini justru bisa
# menjadi bagian istilah. Postgres tidak menyediakan kamus Indonesia
# bawaan, jadi 'simple' adalah pilihan yang benar: cocokkan apa adanya.
TSV_LANGUAGE = "pg_catalog.simple"


def _hybrid_config():
    """Setelan hybrid search bawaan PGVectorStore, memakai RRF.

    Reciprocal Rank Fusion di sini adalah teknik yang sama yang di TX-AI11
    ditulis manual di retrieval/fusion.py - kali ini dijalankan DI DALAM
    basis data, atas seluruh korpus, bukan atas kandidat yang sudah ditarik
    lebih dulu ke memori.
    """
    from langchain_postgres.v2.hybrid_search_config import (
        HybridSearchConfig,
        reciprocal_rank_fusion,
    )

    return HybridSearchConfig(
        tsv_column=TSV_COLUMN,
        tsv_lang=TSV_LANGUAGE,
        fusion_function=reciprocal_rank_fusion,
        primary_top_k=config.N_CANDIDATES,
        secondary_top_k=config.N_CANDIDATES,
    )


"""
CATATAN JEBAKAN - tsv_column WAJIB DIISI.

Bawaan HybridSearchConfig.tsv_column adalah string KOSONG, dan itu
menghasilkan kegagalan yang membingungkan:

  * init_vectorstore_table() tetap membuat kolom "content_tsv" sebagai
    NOT NULL, memakai nama bawaannya sendiri;
  * tetapi add_documents() tidak tahu nama kolom itu, sehingga INSERT
    yang dihasilkannya sama sekali tidak menyertakannya;
  * hasilnya setiap penyisipan ditolak:
        null value in column "content_tsv" violates not-null constraint

Dan bila tabelnya dibuat TANPA hybrid_search_config sejak awal, kolom TSV
tidak pernah ada - lalu menyerahkan hybrid_search_config saat MEMBUKA tidak
memunculkan errors apa pun; pencariannya hanya diam-diam kembali menjadi
vektor murni. Itu bentuk kegagalan yang paling mahal: tidak ada yang rusak,
hanya hasilnya yang lebih buruk tanpa ada yang tahu sebabnya.

Karena itu _hybrid_config() di atas mengisi tsv_column secara eksplisit,
dan setup_table() mengirimkannya saat PEMBUATAN tabel.
"""


def setup_table(dim: int | None = None, timpa: bool = False,
                  hybrid: bool = True) -> None:
    """Sekali saja. Membuat tabel beserta kolom vektornya.

    Dimensi HARUS cocok dengan model embedding: bge-m3 menghasilkan 1024.
    Salah dimensi ditolak saat PENYISIPAN, bukan saat pembuatan tabel -
    galatnya muncul jauh dari penyebabnya, dan pesannya tidak menyebut
    model embedding sama sekali.

    HYBRID HARUS DIMINTA DI SINI, BUKAN SAAT MEMBUKA. Kolom TSV untuk
    pencarian leksikal dibuat bersama tabelnya. Kalau tabel sudah terlanjur
    dibuat tanpa kolom itu, menyerahkan hybrid_search_config saat membuka
    TIDAK menghasilkan errors apa pun - pencariannya hanya diam-diam kembali
    menjadi vektor murni.

    Terbukti di lab: sebelum perbaikan ini, hybrid=True dan hybrid=False
    memberi hasil yang persis sama, dan atribut hybrid_search_config pada
    objek yang terbuka bernilai None. Tidak ada satu pun peringatan.
    """
    _engine().init_vectorstore_table(
        table_name=config.PG_TABLE,
        vector_size=dim or config.EMBEDDING_DIM,
        overwrite_existing=timpa,
        hybrid_search_config=_hybrid_config() if hybrid else None,
    )


def install_hybrid_index() -> None:
    """Indeks GIN pada kolom TSV. Tanpa ini sisi leksikalnya lambat.

    Dijalankan SETELAH penyisipan, dengan alasan yang sama seperti HNSW.
    """
    open_store(hybrid=True).apply_hybrid_search_index()


def _wrap_fts(store):
    """Kosongkan `fts_query` sebelum setiap pencarian.

    JEBAKAN KETIGA, DAN YANG PALING SENYAP. Di langchain-postgres 0.0.17,
    asimilarity_search() mengisi query leksikal dengan MENGUBAH objek
    konfigurasi, dan hanya bila objek itu masih kosong:

        if hybrid_search_config and not hybrid_search_config.fts_query:
            hybrid_search_config.fts_query = query

    Objek konfigurasi itu milik store, dan store dipakai ulang seumur hidup
    proses (lihat retrieval/sumber.py yang men-cache-nya). Akibatnya:

        pencarian ke-1  "Apa isi SE-12/2026?"    -> fts_query = pertanyaan itu
        pencarian ke-2  "Berapa hari cuti?"      -> fts_query MASIH "SE-12"
        pencarian ke-3  ...                      -> MASIH "SE-12"

    Sisi leksikal seluruh sistem terkunci pada pertanyaan pertama yang
    kebetulan diajukan. Tidak ada errors. Hasilnya hanya lebih buruk, dengan
    cara yang mustahil ditebak dari gejalanya.

    Mengosongkannya sebelum tiap pencarian membuat pustaka mengisinya ulang
    dengan pertanyaan yang sedang berjalan.
    """
    original = store.similarity_search

    # Konfigurasinya TIDAK berada di objek PGVectorStore yang kita pegang,
    # melainkan di store async di dalamnya - dan namanya ter-mangle karena
    # atribut privat berawalan dua garis bawah.
    #
    # KENAPA GAGAL KERAS DI SINI, BUKAN DIAM. Kalau langchain-postgres
    # mengganti nama internal ini di versi berikutnya, `getattr(..., None)`
    # akan mengembalikan None, wrapper tidak melakukan apa-apa, dan fts_query
    # basi kembali - persis jebakan senyap yang fungsi ini dibuat untuk
    # menutupnya, sekarang bersembunyi satu lapis lebih dalam. Karena reset
    # ini WAJIB di mode hybrid, ketiadaan internal itu adalah asumsi yang
    # patah, bukan kasus tepi yang boleh dilewati. Ia harus berhenti di
    # konstruksi - tempat yang bisa ditangkap satu tes saat upgrade - bukan
    # di produksi sebagai hasil pencarian yang diam-diam memburuk.
    inner = getattr(store, "_PGVectorStore__vs", None)
    if inner is None or not hasattr(inner, "hybrid_search_config"):
        import langchain_postgres
        raise RuntimeError(
            "Struktur internal PGVectorStore berubah: atribut "
            "'_PGVectorStore__vs.hybrid_search_config' tidak ditemukan "
            f"(langchain-postgres {getattr(langchain_postgres, '__version__', '?')}). "
            "Reset fts_query di _wrap_fts() bergantung padanya. Perbaiki "
            "pemetaan atribut di sini sebelum memakai versi ini - lihat "
            "komentar di atas untuk jebakan yang dijaganya."
        )

    def similarity_search(query, k=None, filter=None, **kwargs):
        inner.hybrid_search_config.fts_query = ""
        return original(query, k=k, filter=filter, **kwargs)

    store.similarity_search = similarity_search
    return store


def open_store(hybrid: bool = True, url: str | None = None):
    """Kembalikan PGVectorStore. hybrid=True memakai RRF bawaan.

    Reciprocal Rank Fusion di sini adalah teknik yang sama yang di TX-AI11
    ditulis manual di retrieval/fusion.py - kali ini dijalankan di dalam
    basis data, pada seluruh korpus, bukan pada kandidat yang sudah diambil
    lebih dulu ke memori.
    """
    from langchain_postgres import PGVectorStore


    # Catatan impor: HybridSearchConfig TIDAK diekspor di tingkat atas
    # langchain_postgres (diperiksa pada 0.0.17) — hanya PGVectorStore dan
    # PGEngine yang ada di sana. Lihat _hybrid_config().
    #
    # Ini jenis kesalahan yang paling membuang waktu di kelas: contoh di
    # banyak tulisan memakai `from langchain_postgres import
    # HybridSearchConfig`, dan galatnya baru muncul saat penyisipan
    # pertama — setelah seluruh embedding selesai dihitung.
    tambahan = {"hybrid_search_config": _hybrid_config()} if hybrid else {}

    store = PGVectorStore.create_sync(
        engine=_engine(url),
        table_name=config.PG_TABLE,
        embedding_service=get_embedding(),
        **tambahan,
    )
    return _wrap_fts(store) if hybrid else store


def insert(chunks: Sequence, hybrid: bool = True) -> int:
    """Bangun embedding seluruh chunks dan simpan. Kembalikan jumlahnya."""
    store = open_store(hybrid=hybrid)
    store.add_documents(list(chunks))
    return len(chunks)


# ------------------------------------------------------------- query mentah

def _direct_connection():
    """Koneksi psycopg biasa, untuk hal-hal yang tidak lewat LangChain.

    Dipakai untuk RLS, siklus hidup indeks, dan penghitungan - semuanya SQL
    murni yang tidak ada padanannya di ui vector store.
    """
    import psycopg

    return psycopg.connect(config.PG_URL_DIRECT)


def vector_count() -> int:
    """Banyaknya baris di tabel chunks."""
    with _direct_connection() as s, s.cursor() as k:
        k.execute(f"SELECT COUNT(*) FROM {config.PG_TABLE}")
        return k.fetchone()[0]


def create_hnsw_index(m: int = 16, ef_construction: int = 64) -> None:
    """Indeks HNSW pada kolom vektor.

    Tanpa ini pencarian tetap BENAR tetapi memindai seluruh tabel. Pada
    korpus lab selisihnya tidak terasa; pada 100.000 chunks ia adalah
    selisih antara 40 milidetik dan 4 detik.

    vector_cosine_ops karena kita memakai kemiripan kosinus - harus cocok
    dengan operator yang dipakai saat mencari, kalau tidak indeksnya
    diabaikan diam-diam.
    """
    from psycopg import sql

    # m dan ef_construction adalah PARAMETER STORAGE DDL, bukan nilai —
    # Postgres menolak parameter terikat di klausa WITH:
    #
    #     syntax error at or near "$1"
    #
    # Jadi keduanya disusun sebagai literal. Dipaksa int() lebih dulu supaya
    # tetap aman meski nilainya datang dari luar.
    with _direct_connection() as s, s.cursor() as k:
        k.execute(sql.SQL(
            "CREATE INDEX IF NOT EXISTS {nama} ON {tabel} "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = {m}, ef_construction = {ef})"
        ).format(
            name=sql.Identifier(f"{config.PG_TABLE}_hnsw"),
            table=sql.Identifier(config.PG_TABLE),
            m=sql.Literal(int(m)),
            ef=sql.Literal(int(ef_construction)),
        ))
        s.commit()


# ------------------------------------------------- siklus hidup indeks (L6)

def mark_revoked(file_name: str) -> int:
    """Tandai seluruh chunks satu dokumen sebagai dicabut.

    Kenapa menandai, bukan menghapus? Karena "kenapa sistem dulu menjawab
    begini?" adalah pertanyaan yang pasti datang, dan hanya bisa dijawab
    kalau datanya masih ada. Penyaring status sudah menahannya dari hasil
    pencarian, jadi tidak ada risiko ia terjawab lagi.
    """
    # PGVectorStore membuat kolomnya bertipe json, BUKAN jsonb — jadi
    # jsonb_set() harus didahului cast, dan hasilnya dikembalikan ke json.
    # Tanpa cast: "function jsonb_set(json, unknown, unknown) does not exist",
    # errors yang menyebut tipe tetapi tidak menyebut kolom mana penyebabnya.
    with _direct_connection() as s, s.cursor() as k:
        k.execute(
            f"UPDATE {config.PG_TABLE} "
            f"SET langchain_metadata = jsonb_set("
            f"    langchain_metadata::jsonb, '{{status}}', %s)::json "
            f"WHERE langchain_metadata->>'source' = %s",
            (f'"{config.REVOKED_STATUS}"', file_name),
        )
        s.commit()
        return k.rowcount


def delete_by_source(file_name: str) -> int:
    """Buang seluruh chunks satu dokumen dari indeks."""
    with _direct_connection() as s, s.cursor() as k:
        k.execute(
            f"DELETE FROM {config.PG_TABLE} "
            f"WHERE langchain_metadata->>'source' = %s",
            (file_name,),
        )
        s.commit()
        return k.rowcount


def stored_fingerprint(file_name: str) -> str | None:
    """Sidik jari isi dokumen saat terakhir diindeks, atau None."""
    with _direct_connection() as s, s.cursor() as k:
        k.execute(
            f"SELECT langchain_metadata->>'sidik' FROM {config.PG_TABLE} "
            f"WHERE langchain_metadata->>'source' = %s LIMIT 1",
            (file_name,),
        )
        row = k.fetchone()
        return row[0] if row else None


# ------------------------------------------------ Row-Level Security (L6)

RLS_INSTALL_SQL = f"""
-- Dua kolom penentu, diisi dari metadata yang sudah ada sejak L3.
ALTER TABLE {config.PG_TABLE} ADD COLUMN IF NOT EXISTS unit        TEXT;
ALTER TABLE {config.PG_TABLE} ADD COLUMN IF NOT EXISTS klasifikasi TEXT DEFAULT 'umum';

-- PROMOSI OTOMATIS metadata -> kolom, LEWAT TRIGGER, bukan hanya sekali.
--
-- Kenapa trigger dan bukan cukup UPDATE di bawah: UPDATE itu hanya membetulkan
-- baris yang SUDAH ada saat RLS dipasang. Dokumen yang diunggak PENGGUNA masuk
-- SETELAH itu, lewat pgvector.insert() (LangChain PGVector) yang hanya menulis
-- langchain_metadata dan TIDAK tahu kolom kustom ini - sehingga unit jatuh ke
-- NULL dan klasifikasi ke default 'umum'. Akibatnya dokumen 'terbatas' yang
-- diunggah menjadi TERLIHAT SEMUA ORANG: gagal-TERBUKA, kebalikan dari yang
-- ditegakkan RLS. Trigger menutup setiap jalur insert/update, sekali untuk
-- selamanya, tanpa bergantung pada pemanggil mengingat mempromosikan sendiri.
CREATE OR REPLACE FUNCTION {config.PG_TABLE}_promosikan_metadata()
RETURNS trigger AS $$
BEGIN
  NEW.unit        := NEW.langchain_metadata->>'unit';
  NEW.klasifikasi := COALESCE(NEW.langchain_metadata->>'klasifikasi', 'umum');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS promosikan_metadata ON {config.PG_TABLE};
CREATE TRIGGER promosikan_metadata
  BEFORE INSERT OR UPDATE ON {config.PG_TABLE}
  FOR EACH ROW EXECUTE FUNCTION {config.PG_TABLE}_promosikan_metadata();

-- Backfill baris yang terlanjur ada (termasuk yang diunggah sebelum trigger
-- ini terpasang dan menjadi 'umum' keliru). Trigger di atas menjaga yang baru.
UPDATE {config.PG_TABLE}
SET    unit        = langchain_metadata->>'unit',
       klasifikasi = COALESCE(langchain_metadata->>'klasifikasi', 'umum');

ALTER TABLE {config.PG_TABLE} ENABLE ROW LEVEL SECURITY;

-- Seseorang melihat dokumen umum, ditambah dokumen terbatas milik unitnya.
DROP POLICY IF EXISTS lihat_sesuai_unit ON {config.PG_TABLE};
CREATE POLICY lihat_sesuai_unit ON {config.PG_TABLE}
FOR SELECT
USING (
  klasifikasi = 'umum'
  OR unit = current_setting('{config.GUC_UNIT}', true)
);
"""


def install_rls() -> None:
    """Pasang kebijakan RLS. Idempoten - aman dijalankan berkali-kali.

    TIGA JEBAKAN yang harus diperagakan di kelas:

    1. Pemilik tabel KEBAL RLS. Kalau lab tersambung sebagai pemilik,
       peragaannya akan menunjukkan angka yang sama untuk kedua users
       dan seluruh pelajarannya hilang. Lihat create_app_role().
    2. Nilai unit TIDAK BOLEH berasal dari pertanyaan users. Ia datang
       dari sesi login. Kalau model bisa memengaruhinya, RLS hanya
       memindahkan lubangnya, bukan menutupnya.
    3. Sitasi bisa membocorkan yang disembunyikan RLS - judul dokumen yang
       muncul di daftar sumber padahal isinya tersaring.
    """
    with _direct_connection() as s, s.cursor() as k:
        k.execute(RLS_INSTALL_SQL)
        s.commit()


def create_app_role(name: str | None = None, password: str | None = None) -> None:
    """Peran non-pemilik yang tunduk pada RLS.

    Jebakan 1 di atas. Peran yang membuat tabel akan melewati seluruh
    kebijakan tanpa satu pun peringatan - peragaan hak akses yang dijalankan
    sebagai pemilik selalu "berhasil", dan itulah yang membuatnya berbahaya.

    Nama dan sandi diambil dari PG_URL_APP secara bawaan, jadi peran yang
    dibuat di sini SELALU cocok dengan yang dipakai aplikasi menyambung -
    lihat config.app_credentials() untuk kenapa itu penting.
    """
    from psycopg import sql

    default_name, default_password = config.app_credentials()
    name = name or default_name
    password = password or default_password

    with _direct_connection() as s, s.cursor() as k:
        k.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
        if not k.fetchone():
            # CREATE ROLE tidak menerima parameter terikat untuk nama peran,
            # jadi namanya disusun lewat psycopg.sql yang meng-escape identifier
            # dengan benar. Jangan pernah menyambungnya dengan f-string.
            k.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password)))
        k.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.Identifier(config.PG_TABLE), sql.Identifier(name)))
        s.commit()


def count_as(unit: str, role: str = "rag_app") -> int:
    """Hitung baris yang TERLIHAT oleh satu unit. Inti peragaan RLS.

    Pertanyaan yang sama, dua users, dua jumlah baris - peragaan yang
    menutup perdebatan keamanan lebih cepat daripada penjelasan apa pun.
    """
    with _direct_connection() as s, s.cursor() as k:
        k.execute(f"SET ROLE {role}")
        k.execute("SELECT set_config(%s, %s, false)", (config.GUC_UNIT, unit))
        k.execute(f"SELECT COUNT(*) FROM {config.PG_TABLE}")
        total_count = k.fetchone()[0]
        k.execute("RESET ROLE")
        return total_count
