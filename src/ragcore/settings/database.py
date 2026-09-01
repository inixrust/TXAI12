"""Storage vektor, URL Postgres, dan nama GUC yang menegakkan RLS.

Nilai kredensial di sini; kebijakan yang menjaganya ada di `security`. Setiap
URL berkredensial melewati `security.secret()`, jadi default demo tidak bisa
lolos ke produksi maupun ke host non-lokal.
"""
from __future__ import annotations

import os

from ragcore.settings.security import maybe_dynamic_db, secret

# --------------------------------------------------- storage vektor
# "pgvector" (bawaan) atau "chroma".
#
# BAWAANNYA pgvector, dan alasannya KEAMANAN. chroma tak mengenal hak-akses
# per-users: pembatasan hanya bergantung pada filter di aplikasi (filter_for) -
# kalau filter itu lupa/tertembus, dokumen terbatas unit lain bocor, tanpa
# jaring pengaman. pgvector menegakkan Row-Level Security di BASIS DATA lewat
# peran rag_app + GUC app.unit_pengguna (lihat PG_URL_APP): setiap query,
# termasuk yang lupa menyaring, tersaring ke unit pemohon. Filter aplikasi
# menjadi lapis KEDUA, RLS lapis KETIGA yang menjaminnya.
#
# chroma tetap disediakan untuk peragaan L2 (membandingkan kedua storage pada
# set uji yang sama) dan untuk jalan tanpa Postgres - setel STORAGE=chroma.
STORAGE: str = os.getenv("STORAGE", "pgvector")

PG_URL: str = secret(
    "PG_URL",
    "postgresql+psycopg://rag:rahasia_lab@localhost:6024/korpus",
)

# Bentuk tanpa "+psycopg" — dipakai LangGraph PostgresSaver, yang memakai
# psycopg langsung dan bukan SQLAlchemy. Dua pustaka, dua tata tulis URL,
# satu basis data yang sama.
PG_URL_DIRECT: str = secret(
    "PG_URL_DIRECT",
    "postgresql://rag:rahasia_lab@localhost:6024/korpus",
)

PG_TABLE: str = "potongan_ncs"

# Sambungan untuk APLIKASI, memakai peran non-pemilik.
#
# INI YANG MEMBUAT RLS BERARTI. Sambungan di atas memakai `rag`, pemilik
# tabel — dan pemilik tabel KEBAL RLS. Selama aplikasi memakai sambungan
# itu, kebijakan hak akses terpasang rapi dan tidak menahan apa pun.
#
# Peran `rag_app` dibuat oleh commands.rls --pasang.
#
# Bila OPENBAO_DB_ROLE diset, user/sandi statis di sini DIGANTI kredensial
# DINAMIS efemeral dari OpenBao (peran anggota rag_app, RLS tetap). Lihat
# security.maybe_dynamic_db dan catatan lease-renewal di sana.
PG_URL_APP: str = maybe_dynamic_db(secret(
    "PG_URL_APP",
    "postgresql+psycopg://rag_app:rahasia_app@localhost:6024/korpus",
))

# Nama parameter sesi yang dibaca kebijakan RLS. Didefinisikan sekali di sini
# karena dipakai di tiga tempat: SQL kebijakan, penyusunan sambungan, dan
# peragaan di kelas. Salah ketik di salah satunya = filters yang diam-diam
# selalu bernilai NULL.
GUC_UNIT: str = "app.unit_pengguna"

# HARUS cocok dengan MODEL_EMBEDDING. bge-m3 menghasilkan 1024 dimensi.
# Kalau model embedding diganti, angka ini ikut berubah DAN tabelnya harus
# DIBUAT ULANG, bukan sekadar diisi ulang. Tidak ada keadaan setengah jalan
# yang benar: separuh tabel berisi vektor model lama akan memberi peringkat
# yang tampak wajar tetapi salah, tanpa satu pun errors.
EMBEDDING_DIM: int = 1024
