"""Antrean tugas ingest di dalam PostgreSQL (L6 lanjutan).

KENAPA ANTREANNYA DI BASIS DATA, BUKAN DI REDIS.

Silabus pembanding menyebut "queue + workers, e.g. Redis workers", dan Redis
memang pilihan yang lazim. Di lab ini antreannya ditaruh di PostgreSQL yang
SUDAH ADA, dan itu keputusan sadar dengan dua alasan:

  1. Nol container baru. Laptop peserta sudah menjalankan Oracle, PostgreSQL,
     enam container Langfuse, dan Ollama. Menambah Redis berarti menambah
     tekanan memori pada mesin yang modelnya sudah tumpah ke CPU.
  2. `SELECT ... FOR UPDATE SKIP LOCKED` adalah pola queue produksi yang
     sah dan dipakai luas. Yang perlu dipelajari peserta - pekerja terpisah,
     retrieval tugas yang aman untuk banyak worker, status yang terlihat,
     dan tugas yang macet - identik pada kedua pilihan.

Yang HILANG dengan pilihan ini juga perlu diucapkan: queue di basis data
ikut menanggung beban basis data, dan pada laju sangat tinggi ia kalah dari
broker khusus. Untuk arsip organisasi yang bertambah puluhan dokumen per
hari, laju itu tidak pernah tercapai.
"""
from __future__ import annotations

from typing import Any

import psycopg

from .. import config

TABLE = "tugas_ingest"

# Status tugas. Sengaja sedikit dan sengaja eksplisit.
WAITING = "menunggu"
PROCESSING = "diproses"
DONE = "selesai"
FAILED = "gagal"

# Berapa lama sebuah tugas boleh berstatus `diproses` sebelum dianggap macet.
#
# Pekerja yang mati mendadak - Ctrl-C, laptop tertutup, proses dibunuh -
# meninggalkan tugasnya berstatus `diproses` SELAMANYA. Tanpa batas ini,
# dokumen itu tidak akan pernah diindeks dan tidak akan pernah dilaporkan
# gagal: ia hanya diam. Ekstraksi VLM satu dokumen bisa memakan belasan
# menit, jadi batasnya harus longgar.
STUCK_LIMIT_MINUTES = 45

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
  id          BIGSERIAL PRIMARY KEY,
  nama_berkas TEXT        NOT NULL,
  jalur       TEXT        NOT NULL,
  jenis       TEXT        NOT NULL DEFAULT 'sop',
  -- Kewenangan dokumen, DITANGKAP SAAT UNGGAH dari identitas pengunggah.
  -- Lihat catatan panjang di kirim().
  unit        TEXT,
  klasifikasi TEXT        NOT NULL DEFAULT 'terbatas',
  -- NIP pengunggah. Dipakai UI untuk menampilkan HANYA unggahan milik
  -- orang yang sedang login - status "dokumen SAYA sudah masuk?" adalah
  -- pertanyaan per-orang, bukan papan pengumuman antrean seluruh kantor.
  -- NULL untuk tugas dari CLI/operator (tanpa identitas pengunggah).
  pengunggah  TEXT,
  status      TEXT        NOT NULL DEFAULT '{WAITING}',
  pesan       TEXT,
  potongan    INTEGER,
  worker      TEXT,
  dibuat      TIMESTAMPTZ NOT NULL DEFAULT now(),
  dimulai     TIMESTAMPTZ,
  selesai     TIMESTAMPTZ
);

-- Kolom kewenangan ditambahkan belakangan; ALTER agar tabel yang sudah
-- terlanjur dibuat ikut terbawa tanpa perlu dihapus.
ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS unit TEXT;
ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS klasifikasi TEXT
      NOT NULL DEFAULT 'terbatas';
ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS pengunggah TEXT;

-- Kolom `pekerja` berganti nama menjadi `worker`. Tabel yang sudah
-- terlanjur dibuat ikut dibawa, bukan dipaksa dihapus: antrean bisa saja
-- memuat tugas yang belum selesai saat pembaruan ini dijalankan.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
              WHERE table_name = '{TABLE}' AND column_name = 'pekerja') THEN
    EXECUTE 'ALTER TABLE {TABLE} RENAME COLUMN pekerja TO worker';
  END IF;
END $$;

-- Pengambilan tugas selalu mencari yang paling lama menunggu.
CREATE INDEX IF NOT EXISTS {TABLE}_antre ON {TABLE} (status, dibuat);
"""


def _connect():
    """Sambungan PEMILIK, bukan sambungan aplikasi.

    Antrean adalah infrastruktur, bukan data users: ia tidak tunduk RLS
    dan memang tidak boleh. Yang tunduk RLS adalah chunks dokumen yang
    dihasilkannya.
    """
    return psycopg.connect(
        config.PG_URL.replace("postgresql+psycopg://", "postgresql://"))


def setup() -> None:
    """Buat tabel queue bila belum ada. Aman dijalankan berulang."""
    with _connect() as c:
        c.execute(DDL)


def send(file_name: str, file_path: str, kind: str = "sop",
          unit: str | None = None, classification: str = "terbatas",
          pengunggah: str | None = None) -> int:
    """Masukkan satu berkas ke queue. Kembalikan id tugas.

    KEWENANGAN DITANGKAP DI SINI, SAAT UNGGAH - bukan disimpulkan dari nama
    berkas saat indexing, dan bukan ditambahkan belakangan.

    Pada pipeline batch, `penanda.kepemilikan()` menurunkan unit dan
    klasifikasi dari AWALAN NAMA BERKAS, memakai peta yang dipelihara
    operator. Itu cukup selama korpusnya dikurasi. Begitu users boleh
    mengunggah sendiri, cara itu gagal dengan cara yang berbahaya: nama yang
    tidak dikenal jatuh ke nilai bawaan, dan nilai bawaannya adalah
    `klasifikasi=umum` - TERLIHAT SEMUA ORANG.

    Terbukti di lab ini: berkas bernama "uji-unggah.pdf" masuk indeks dengan
    unit=Umum, klasifikasi=umum. Isinya SOP-05 milik Divisi TI.

    Karena itu jalur unggah GAGAL TERTUTUP: klasifikasi bawaannya `terbatas`,
    dan unitnya diambil dari pengunggah. Dokumen yang salah ditandai terbatas
    hanya merepotkan satu orang yang lalu memintanya dibuka; dokumen yang
    salah ditandai umum sudah terlanjur terbaca semua orang.
    """
    setup()
    with _connect() as c:
        row = c.execute(
            f"INSERT INTO {TABLE} "
            f"(nama_berkas, jalur, jenis, unit, klasifikasi, pengunggah) "
            f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (file_name, file_path, kind, unit, classification,
             pengunggah)).fetchone()
        return row[0]


def claim_one(worker: str) -> dict[str, Any] | None:
    """Ambil satu tugas dan tandai sedang diproses. None bila queue kosong.

    SKIP LOCKED ADALAH INTI FUNGSI INI.

    Tanpa `FOR UPDATE SKIP LOCKED`, dua pekerja yang berjalan bersamaan akan
    membaca baris yang SAMA, keduanya menandainya `diproses`, dan dokumen itu
    diekstrak dua kali - dua kali biaya VLM, dan chunks ganda di indeks.

    Dengan SKIP LOCKED, pekerja kedua MELEWATI baris yang sedang dikunci
    pekerja pertama dan langsung mengambil tugas berikutnya. Tidak ada yang
    menunggu, dan tidak ada yang bertabrakan.

    Tugas yang MACET ikut diambil di sini, bukan lewat proses pembersih
    terpisah: bila sebuah tugas berstatus `diproses` melewati STUCK_LIMIT_MINUTES,
    pekerja mana pun boleh mengambilnya kembali. Pemulihan yang menumpang pada
    jalur yang sudah pasti dijalankan lebih tahan daripada pemulihan yang
    bergantung pada proses lain yang mungkin juga mati.
    """
    setup()
    with _connect() as c:
        row = c.execute(
            f"""
            WITH berikutnya AS (
                SELECT id FROM {TABLE}
                 WHERE status = %s
                    OR (status = %s
                        AND dimulai < now() - interval '{STUCK_LIMIT_MINUTES} minutes')
                 ORDER BY dibuat
                 FOR UPDATE SKIP LOCKED
                 LIMIT 1
            )
            UPDATE {TABLE} t
               SET status = %s, dimulai = now(), worker = %s
              FROM berikutnya b
             WHERE t.id = b.id
         RETURNING t.id, t.nama_berkas, t.jalur, t.jenis, t.unit,
                   t.klasifikasi, t.pengunggah
            """,
            (WAITING, PROCESSING, PROCESSING, worker)).fetchone()
    if not row:
        return None
    return {"id": row[0], "nama_berkas": row[1], "jalur": row[2],
            "jenis": row[3], "unit": row[4], "klasifikasi": row[5],
            "pengunggah": row[6]}


def finish(task_id: int, chunks: int) -> None:
    """Tandai tugas selesai beserta jumlah chunks yang dihasilkannya."""
    with _connect() as c:
        c.execute(
            f"UPDATE {TABLE} SET status=%s, potongan=%s, selesai=now(), "
            f"pesan=NULL WHERE id=%s", (DONE, chunks, task_id))


def fail(task_id: int, message: str) -> None:
    """Tandai tugas gagal BESERTA sebabnya.

    Sebabnya disimpan, bukan hanya dicetak ke log pekerja. Pengguna yang
    mengunggah berkas tidak membaca log pekerja - ia melihat ui, dan
    yang harus terbaca di sana adalah "kenapa dokumen saya tidak masuk".
    """
    with _connect() as c:
        c.execute(
            f"UPDATE {TABLE} SET status=%s, pesan=%s, selesai=now() "
            f"WHERE id=%s", (FAILED, message[:500], task_id))


def listing(limit: int = 20,
            pengunggah: str | None = None) -> list[dict[str, Any]]:
    """Tugas terakhir beserta statusnya, untuk ditampilkan ke users.

    Bila `pengunggah` (NIP) diberikan, HANYA tugas milik orang itu yang
    dikembalikan - itulah yang membuat panel unggah menjawab "dokumen SAYA
    sudah masuk?" alih-alih memamerkan antrean seluruh kantor. Tanpa filter
    (mis. untuk operator/CLI), seluruh antrean terlihat seperti sebelumnya.
    """
    setup()
    where = "WHERE pengunggah = %s " if pengunggah is not None else ""
    args: tuple = (pengunggah, limit) if pengunggah is not None else (limit,)
    with _connect() as c:
        row = c.execute(
            f"SELECT id, nama_berkas, jenis, status, pesan, potongan, "
            f"dibuat, dimulai, selesai FROM {TABLE} "
            f"{where}ORDER BY id DESC LIMIT %s", args).fetchall()
    column = ("id", "nama_berkas", "jenis", "status", "pesan", "potongan",
             "dibuat", "dimulai", "selesai")
    return [dict(zip(column, b, strict=False)) for b in row]


def for_panel(pengunggah: str | None,
              session_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """Unggahan untuk panel UI - SENGAJA TIDAK MENAMPILKAN RIWAYAT PERMANEN.

    Panel ini menjawab "dokumen saya sedang/sudah diproses?" - pertanyaan yang
    umurnya pendek. Menariknya dari `listing(pengunggah=...)` membuat setiap
    unggahan `selesai` MENETAP selamanya di layar, padahal begitu user melihat
    'selesai' informasinya sudah usai. Karena itu yang ditampilkan hanya:

      - tugas yang MASIH berjalan (menunggu/diproses) milik user ini - supaya
        unggahan yang belum kelar tak hilang saat halaman dimuat ulang; dan
      - tugas yang diunggah pada SESI berjalan (session_ids, dilacak di
        session_state UI) - supaya user melihat transisinya menjadi 'selesai'
        sekali, lalu daftar itu bersih dengan sendirinya pada muat ulang.

    Tugas 'selesai' dari sesi lama TIDAK muncul: ia tetap ada di tabel sebagai
    catatan infrastruktur/audit, tapi tak lagi dipamerkan ke user.
    """
    setup()
    ids = [int(i) for i in (session_ids or [])]
    # Query disusun bercabang, bukan selalu memakai ANY: daftar id kosong
    # sebagai array kosong bisa membuat psycopg gagal menentukan tipenya.
    if ids:
        cond = "(pengunggah = %s AND status IN (%s, %s)) OR id = ANY(%s)"
        args: tuple = (pengunggah, WAITING, PROCESSING, ids)
    else:
        cond = "pengunggah = %s AND status IN (%s, %s)"
        args = (pengunggah, WAITING, PROCESSING)
    with _connect() as c:
        row = c.execute(
            f"SELECT id, nama_berkas, jenis, status, pesan, potongan "
            f"FROM {TABLE} WHERE {cond} ORDER BY id DESC LIMIT 20",
            args).fetchall()
    column = ("id", "nama_berkas", "jenis", "status", "pesan", "potongan")
    return [dict(zip(column, b, strict=False)) for b in row]


def summarize() -> dict[str, int]:
    """Jumlah tugas per status."""
    setup()
    with _connect() as c:
        return {s: n for s, n in c.execute(
            f"SELECT status, count(*) FROM {TABLE} GROUP BY status")}
