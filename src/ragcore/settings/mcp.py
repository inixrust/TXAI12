"""Server MCP Oracle: perintah peluncur, SQLcl, dan sambungan tersimpan."""
from __future__ import annotations

import os

from ragcore.settings.security import secret

# ------------------------------------------------------------------- MCP
# Perintah untuk menjalankan server MCP Oracle.
#
# Bawaannya `sql -mcp`, yang benar bila SQLcl ada di PATH dan dijalankan
# dari terminal sungguhan. Bisa ditimpa lewat MCP_COMMAND karena skrip
# peluncur SQLcl MENUNTUT konsol interaktif: dijalankan dari proses tanpa
# TTY (CI, agen otomatis, sebagian IDE) ia gagal dengan
#
#     java.io.IOException: Incorrect function
#
# padahal mode -mcp sendiri tidak butuh konsol sama sekali. Jalan keluarnya
# memanggil kelas utamanya langsung — lihat SQLCL_HOME di bawah.
MCP_COMMAND: list[str] = (
    os.getenv("MCP_COMMAND", "").split() or ["sql", "-mcp"]
)

# Bila diisi, MCP_COMMAND disusun otomatis memakai java + jar SQLcl,
# lengkap dengan --add-opens yang biasanya dipasang skrip peluncurnya.
SQLCL_HOME: str = os.getenv("SQLCL_HOME", "")

# Nama sambungan TERSIMPAN yang dipakai agent.
#
# Tool `connect` pada server MCP hanya menerima NAMA — ia tidak bisa diberi
# user/sandi. Jadi sambungan ini harus disimpan lebih dulu, sekali saja:
#
#     python -m ragcore.commands.mcp --simpan-sambungan
#
# Lihat oracle/README.md untuk alasannya dan untuk cara manualnya.
MCP_CONNECTION_NAME: str = os.getenv("MCP_CONNECTION_NAME", "agentlab")

# Kredensial yang disimpan. Akun HANYA-BACA (rag_baca), bukan pemilik data —
# lihat empat lapis pembatas di oracle/02-restrictions.sql.
ORACLE_CONNECTION: str = secret(
    "ORACLE_CONNECTION",
    "rag_baca/Rahasia_Lab_2026@localhost:1521/FREEPDB1",
)

# AKUN OPERATOR TERPISAH (penutupan penuh F-02, oracle/04-operator-account.sql).
#
# rag_baca (di atas) tak boleh 'lihat semua' — set_operator menolaknya di DB.
# Jalur non-produksi yang MEMANG operator (CLI, evaluasi) memakai koneksi ini,
# yang menyimpan kredensial rag_operator. Bila belum disiapkan, keduanya jatuh
# ke koneksi/kredensial rag_baca — perilaku lama, tanpa kejutan, dan set_operator
# akan gagal-tutup (fail-closed) alih-alih diam-diam lihat-semua.
MCP_CONNECTION_OPERATOR: str = os.getenv(
    "MCP_CONNECTION_OPERATOR", MCP_CONNECTION_NAME)
ORACLE_CONNECTION_OPERATOR: str = secret(
    "ORACLE_CONNECTION_OPERATOR", ORACLE_CONNECTION)

# AKUN AUTENTIKASI hak-minimal (rag_auth, oracle/05-auth.sql).
#
# Dipakai HANYA oleh jalur login (domain/auth.py) untuk membaca hash sandi
# argon2id dari ncs.pengguna_auth dan identitas dari ncs.karyawan. Sengaja
# TERPISAH dari rag_baca: kredensial yang dipakai MENJAWAB pertanyaan tak boleh
# bisa membaca hash sandi. Format easy-connect (user/sandi@host:port/service),
# dibaca oleh python-oracledb thin - lihat domain/auth.py.
ORACLE_CONNECTION_AUTH: str = secret(
    "ORACLE_CONNECTION_AUTH",
    "rag_auth/Rahasia_Lab_2026@localhost:1521/FREEPDB1",
)
