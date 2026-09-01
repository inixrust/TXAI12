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


# --------------------------------------------------------- OpenBao (opsional)
#
# Sumber rahasia PRODUKSI, menggantikan nilai plaintext di .env. OpenBao = fork
# open-source (MPL 2.0, Linux Foundation) dari HashiCorp Vault, API-compatible -
# sejalan dengan pilihan lab memakai perkakas FOSS yang bisa di-selfhost (lihat
# alasan memilih Langfuse ketimbang LangSmith di tracing.py).
#
# Yang disetel lewat env di sini AMAN di env: alamat & token AKSES ke OpenBao,
# BUKAN kredensial DB itu sendiri. Rahasia sebenarnya (URL DB, kunci HMAC) hidup
# di dalam OpenBao dan diambil saat impor, sekali, lalu di-cache.
#
#   OPENBAO_ADDR       mis. https://openbao:8200
#   OPENBAO_KV_PATH    jalur KV v2, default 'secret/data/txai12'
#
# IDENTITAS APP KE OpenBao - dua cara, AppRole didahulukan:
#   OPENBAO_ROLE_ID + OPENBAO_SECRET_ID  -> login AppRole, dapat token pendek
#                    (OPENBAO_SECRET_ID_FILE juga didukung: baca secret_id dari
#                    berkas yang di-mount, lebih baik daripada di env).
#   OPENBAO_TOKEN    -> token statis (uji/darurat). Menang bila diisi.
#
# Kenapa AppRole > token statis: token statis yang tak diperbarui KEDALUWARSA -
# restart container setelah itu gagal mengambil rahasia. Dengan AppRole, app
# LOGIN SEGAR tiap start memakai role_id + secret_id (berumur panjang), lalu
# dapat token pendek untuk sesi itu. Inilah identitas app yang dianjurkan.
#
# Urutan sumber tetap: env -> OpenBao -> (produksi: gagal / lab: default). Env
# menimpa. OpenBao MATI tidak mematikan app - jatuh ke jalur berikutnya.
_bao_cache: dict | None = None


def _approle_login(addr: str) -> str:
    """Token dari login AppRole (role_id + secret_id). '' bila tak dikonfigurasi.

    secret_id boleh dari env ATAU berkas (OPENBAO_SECRET_ID_FILE) - berkas yang
    di-mount lebih aman daripada rahasia di environment.
    """
    role_id = os.getenv("OPENBAO_ROLE_ID", "").strip()
    secret_id = os.getenv("OPENBAO_SECRET_ID", "").strip()
    if not secret_id:
        berkas = os.getenv("OPENBAO_SECRET_ID_FILE", "").strip()
        if berkas:
            try:
                with open(berkas, encoding="utf-8") as f:
                    secret_id = f.read().strip()
            except OSError:
                return ""
    if not addr or not role_id or not secret_id:
        return ""
    import json
    import urllib.request
    try:
        data = json.dumps({"role_id": role_id, "secret_id": secret_id}).encode()
        req = urllib.request.Request(
            f"{addr.rstrip('/')}/v1/auth/approle/login",
            data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:   # noqa: S310
            body = json.load(r)
        return (body.get("auth") or {}).get("client_token", "") or ""
    except Exception:
        return ""


def _openbao_secrets() -> dict:
    """Rahasia dari OpenBao KV v2, di-cache. {} bila tak dikonfigurasi/terjangkau."""
    global _bao_cache
    if _bao_cache is not None:
        return _bao_cache
    addr = os.getenv("OPENBAO_ADDR", "").strip()
    path = os.getenv("OPENBAO_KV_PATH", "secret/data/txai12").strip()
    # Token statis menang; bila kosong, coba login AppRole.
    token = os.getenv("OPENBAO_TOKEN", "").strip() or _approle_login(addr)
    if not addr or not token:
        _bao_cache = {}
        return _bao_cache
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{addr.rstrip('/')}/v1/{path.lstrip('/')}",
            headers={"X-Vault-Token": token})
        with urllib.request.urlopen(req, timeout=5) as r:   # noqa: S310 (host dikonfigurasi operator)
            body = json.load(r)
        _bao_cache = (body.get("data") or {}).get("data") or {}
    except Exception:
        # Fail-safe: secret store mati tak boleh mematikan app. Jatuh ke env/
        # default; produksi tetap fail-closed bila rahasianya akhirnya kosong.
        _bao_cache = {}
    return _bao_cache


def _sourced(name: str) -> str:
    """Nilai dari env (menang) atau OpenBao. '' bila tak ada di keduanya."""
    return (os.getenv(name, "").strip()
            or str(_openbao_secrets().get(name) or "").strip())


# ------------------------------------------------- kredensial DB DINAMIS
#
# Alih-alih sandi DB STATIS di KV, OpenBao bisa MENERBITKAN user+sandi efemeral
# per-lease (secrets engine 'database'). Peran dinamis dibuat sebagai ANGGOTA
# rag_app, jadi RLS tetap berlaku (terbukti: kredensial dinamis pun hanya melihat
# baris unitnya). Diaktifkan dengan OPENBAO_DB_ROLE=<nama-role>.
#
# BATAS JUJUR (lease renewal): kredensial diambil SEKALI saat impor. Ia berlaku
# selama TTL lease (mis. 1 jam). Proses yang hidup lebih lama dari TTL akan
# gagal membuat sambungan BARU setelah lease berakhir - produksi butuh perpanjang
# lease (renewer latar) atau ambil-ulang saat sambungan gagal. Untuk lab, setel
# TTL cukup panjang / restart dalam TTL. Karena itu ini OPT-IN, bukan bawaan.


# State lease dinamis - dipakai renewer latar (start_lease_renewer). base_url
# menyimpan URL STATIS (dengan placeholder kredensial) supaya rotasi bisa
# menyusun ulang dengan kredensial baru tanpa kehilangan host/port/db.
_dynamic: dict = {"lease_id": None, "ttl": 0, "role": "", "base_url": ""}
_renewer_started = False


def _dynamic_db_creds(role: str) -> tuple[str, str] | None:
    """(user, sandi) efemeral dari OpenBao database/creds/<role>. None bila gagal.

    Sekaligus MENCATAT lease_id + TTL supaya bisa diperpanjang/dirotasi.
    """
    addr = os.getenv("OPENBAO_ADDR", "").strip()
    token = os.getenv("OPENBAO_TOKEN", "").strip() or _approle_login(addr)
    if not addr or not token:
        return None
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{addr.rstrip('/')}/v1/database/creds/{role}",
            headers={"X-Vault-Token": token})
        with urllib.request.urlopen(req, timeout=5) as r:   # noqa: S310
            body = json.load(r)
        data = body.get("data") or {}
        user, pw = data.get("username"), data.get("password")
        if not (user and pw):
            return None
        _dynamic.update(lease_id=body.get("lease_id"),
                        ttl=int(body.get("lease_duration") or 0), role=role)
        return (user, pw)
    except Exception:
        return None


def _with_creds(url: str, user: str, pw: str) -> str:
    """Ganti userinfo di URL, biarkan host/port/db apa adanya."""
    from urllib.parse import quote, urlsplit, urlunsplit

    parts = urlsplit(url)
    netloc = f"{quote(user, safe='')}:{quote(pw, safe='')}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def maybe_dynamic_db(url: str) -> str:
    """Ganti user/sandi di URL dengan kredensial DINAMIS bila OPENBAO_DB_ROLE diset.

    Fail-safe: bila pengambilan gagal, kembalikan URL apa adanya (kredensial
    statisnya). Hostname/port/nama-basis-data tidak diubah.
    """
    role = os.getenv("OPENBAO_DB_ROLE", "").strip()
    if not role:
        return url
    _dynamic["base_url"] = url            # simpan bentuk statis untuk rotasi
    creds = _dynamic_db_creds(role)
    if not creds:
        return url
    return _with_creds(url, *creds)


def _renew_lease() -> int:
    """Perpanjang lease dinamis saat ini. Kembalikan TTL baru (detik); 0 bila
    gagal / tak ada lease / tak bisa diperpanjang lagi (mendekati max_ttl)."""
    addr = os.getenv("OPENBAO_ADDR", "").strip()
    lease_id = _dynamic.get("lease_id")
    if not addr or not lease_id:
        return 0
    token = os.getenv("OPENBAO_TOKEN", "").strip() or _approle_login(addr)
    if not token:
        return 0
    import json
    import urllib.request
    try:
        payload = json.dumps({"lease_id": lease_id,
                              "increment": _dynamic.get("ttl") or 3600}).encode()
        req = urllib.request.Request(
            f"{addr.rstrip('/')}/v1/sys/leases/renew",
            data=payload, headers={"X-Vault-Token": token})
        with urllib.request.urlopen(req, timeout=5) as r:   # noqa: S310
            body = json.load(r)
        ttl = int(body.get("lease_duration") or 0)
        if ttl:
            _dynamic["ttl"] = ttl
        return ttl
    except Exception:
        return 0


def _rotate_dynamic() -> bool:
    """Ambil kredensial dinamis BARU dan pasang ke config.PG_URL_APP. True bila
    berhasil. Dipakai saat lease tak bisa diperpanjang lagi."""
    role = _dynamic.get("role")
    base = _dynamic.get("base_url")
    if not role or not base:
        return False
    creds = _dynamic_db_creds(role)
    if not creds:
        return False
    new_url = _with_creds(base, *creds)
    try:
        import ragcore.config as C
        C.PG_URL_APP = new_url
        from ragcore.settings import database
        database.PG_URL_APP = new_url
    except Exception:
        return False
    return True


def refresh_dynamic_db(min_ttl: int = 600) -> str:
    """Satu langkah pemeliharaan lease: perpanjang; bila tak bisa (mendekati
    max_ttl) ATAU TTL hasil perpanjangan di bawah `min_ttl`, ROTASI ke kredensial
    baru. Kembalikan 'renewed' / 'rotated' / 'gagal'. Fungsi murni-ish (tanpa
    tidur) supaya bisa diuji langsung."""
    ttl = _renew_lease()
    if ttl >= min_ttl:
        return "renewed"
    return "rotated" if _rotate_dynamic() else "gagal"


def start_lease_renewer() -> bool:
    """Jalankan thread latar yang menjaga kredensial DB dinamis tetap segar
    (perpanjang; rotasi bila mendekati max_ttl). Tak melakukan apa-apa bila
    kredensial dinamis tak dipakai. Kembalikan True bila thread dimulai.

    Ini yang menutup 'batas jujur' sebelumnya: proses berumur panjang tak lagi
    putus saat lease berakhir.
    """
    global _renewer_started
    if _renewer_started:
        return False              # Streamlit menjalankan ulang skrip - jangan
    if not os.getenv("OPENBAO_DB_ROLE", "").strip() or not _dynamic.get("lease_id"):
        return False
    import threading
    import time

    _renewer_started = True

    def _loop():
        while True:
            ttl = _dynamic.get("ttl") or 3600
            time.sleep(max(30, int(ttl * 0.6)))   # bangun sebelum kedaluwarsa
            try:
                refresh_dynamic_db()
            except Exception:
                pass

    threading.Thread(target=_loop, daemon=True, name="bao-lease-renewer").start()
    return True


def secret(name: str, lab_default: str) -> str:
    """Ambil kredensial: env -> OpenBao -> default (hanya lab).

    Di produksi (RAG_ENV=production) default diabaikan: yang tak diset di env
    MAUPUN OpenBao menggagalkan impor. Di lab, default dipakai tetapi ditolak
    bila ia menunjuk host non-lokal - lihat _guard_secret().
    """
    value = _sourced(name)
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

    Sama seperti secret() dalam hal produksi WAJIB dari environment/OpenBao,
    tetapi TANPA penjaga host: nilainya rahasia HMAC, bukan URL, jadi tak ada
    host untuk diperiksa. Memakai secret() di sini akan salah - ia mencoba
    mengurai host dari sebuah rahasia acak.
    """
    value = _sourced(name)
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
