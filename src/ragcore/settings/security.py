"""Mode produksi dan kebijakan rahasia — dipisahkan SENGAJA dari nilai-nilai.

Ini satu-satunya tempat yang memutuskan apakah sebuah kredensial boleh dipakai.
Nilai kredensialnya sendiri ada di `database` dan `mcp`; keduanya memanggil
`secret()` di sini. Memisahkan kebijakan dari nilai berarti logika keamanan
bisa ditinjau di satu berkas, tanpa terselip di antara knob DPI dan ukuran
chunk.
"""
from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

# --------------------------------------------------------------- mode
#
# Lab HARUS jalan tanpa setup: `docker compose up` lalu perintah pertama,
# tanpa mengisi apa pun. Karena itu kredensial di database/mcp punya default -
# tetapi default itu kredensial DEMO yang ikut masuk git, image, dan log.
#
# Dua penjaga membuat default itu aman:
#
#   1. RAG_ENV=production  -> setiap rahasia WAJIB dari environment. Yang
#      kosong menggagalkan proses SAAT IMPOR, dengan pesan yang menyebut
#      nama variabelnya - bukan gagal jauh di dalam pustaka basis data.
#
#   2. Selalu aktif, apa pun modenya: bila host BUKAN localhost tetapi
#      sandinya masih sandi demo, itu artinya seseorang menunjuk basis data
#      sungguhan sambil lupa mengganti kredensial. Ditolak - inilah kebocoran
#      yang paling mungkin terjadi di lapangan.
#
# Pola yang sama dipakai kerangka kerja dewasa (DEBUG Django, env Rails):
# permisif untuk pengembangan lokal, fail-closed untuk produksi.
RAG_ENV: str = os.getenv("RAG_ENV", "lab").strip().lower()
IS_PRODUCTION: bool = RAG_ENV in {"production", "produksi", "prod"}

_DEMO_SECRETS = ("rahasia_lab", "rahasia_app", "Rahasia_Lab_2026")

# Host yang dianggap "lab": localhost dan nama layanan di dalam compose.
# Nama HARUS dicocokkan utuh, bukan substring - '@db' yang dicocokkan sebagai
# substring akan salah menerima '@db.internal' sebagai lokal (bug ini benar-
# benar lolos di percobaan pertama, dan hanya tes yang menangkapnya).
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db", "postgres",
                          "oracle", "pg-txai12", "oracle-txai12"})


class ConfigError(RuntimeError):
    """Setelan yang membuat sistem tidak aman untuk dijalankan."""


def _host_of(value: str) -> str:
    """Ambil hostname dari URL SQLAlchemy atau easy-connect Oracle."""
    after_at = value.rsplit("@", 1)[-1]           # buang kredensial
    host = after_at.split("/", 1)[0].split(":", 1)[0]
    return host.strip().lower()


def _guard_secret(name: str, value: str) -> str:
    """Tolak sandi demo yang dipakai terhadap host non-lokal.

    Berlaku di SEMUA mode: kombinasi ini hampir selalu berarti 'menunjuk
    basis data sungguhan tapi lupa mengganti sandi', dan itu kebocoran.
    """
    non_lokal = _host_of(value) not in _LOCAL_HOSTS
    if non_lokal and any(demo in value for demo in _DEMO_SECRETS):
        raise ConfigError(
            f"{name} memakai sandi demo terhadap host non-lokal "
            f"({_host_of(value)}).\n"
            f"  Ini kredensial contoh yang ada di kode dan .env.example.\n"
            f"  Ganti dengan kredensial sungguhan sebelum menunjuk basis data\n"
            f"  di luar container lab.")
    return value


def secret(name: str, lab_default: str) -> str:
    """Ambil kredensial dari environment, dengan default HANYA untuk lab.

    Di produksi (RAG_ENV=production) default diabaikan: variabel yang tidak
    disetel menggagalkan impor. Di lab, default dipakai tetapi ditolak bila
    ia menunjuk host non-lokal - lihat _guard_secret().
    """
    value = os.getenv(name, "").strip()
    if value:
        return _guard_secret(name, value)
    if IS_PRODUCTION:
        raise ConfigError(
            f"{name} tidak disetel, padahal RAG_ENV=production.\n"
            f"  Kredensial demo TIDAK dipakai di produksi. Setel {name} lewat\n"
            f"  environment atau secret manager sebelum menjalankan.")
    return _guard_secret(name, lab_default)


def signing_secret(name: str, lab_default: str) -> str:
    """Rahasia untuk MENANDATANGANI token (mis. sesi login), bukan kredensial DB.

    Sama seperti secret() dalam hal produksi WAJIB dari environment, tetapi
    TANPA penjaga host: nilainya rahasia HMAC, bukan URL, jadi tak ada host
    untuk diperiksa. Memakai secret() di sini akan salah - ia mencoba mengurai
    host dari sebuah rahasia acak.
    """
    value = os.getenv(name, "").strip()
    if value:
        return value
    if IS_PRODUCTION:
        raise ConfigError(
            f"{name} tidak disetel, padahal RAG_ENV=production.\n"
            f"  Token sesi ditandatangani dengan rahasia ini; default lab\n"
            f"  TIDAK dipakai di produksi - siapa pun yang tahu default itu\n"
            f"  bisa memalsukan sesi. Setel {name} lewat environment.")
    return lab_default


def app_credentials() -> tuple[str, str]:
    """(user, password) yang dipakai aplikasi untuk sambungan RLS.

    Diambil dari PG_URL_APP supaya peran yang DIBUAT commands.rls --pasang
    memakai sandi yang SAMA dengan yang dipakai aplikasi untuk menyambung.
    Sebelumnya keduanya punya default 'rahasia_app' sendiri-sendiri: di
    produksi, orang menyetel PG_URL_APP dengan sandi sungguhan, menjalankan
    --pasang, dan peran justru dibuat dengan sandi demo - aplikasi lalu gagal
    menyambung, tanpa petunjuk bahwa sumbernya dua nilai yang berbeda.
    """
    from ragcore.settings.database import PG_URL_APP

    parsed = urlparse(PG_URL_APP.replace("+psycopg", ""))
    user = unquote(parsed.username or "rag_app")
    password = unquote(parsed.password or "")
    return user, password
