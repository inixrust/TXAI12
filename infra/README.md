# Infra produksi TX-AI12 (kerangka)

Kerangka pengerasan untuk menjalankan TX-AI12 di luar lab: **manajemen rahasia
(OpenBao)** menggantikan rahasia plaintext di `.env`, dan **satu pintu masuk
ber-TLS (Caddy)** di depan aplikasi. Ini melengkapi compose yang sudah ada
(`compose-oracle.yaml`, `compose-pgvector.yaml`, stack Langfuse) - bukan
menggantikannya.

Ini **kerangka**, bukan tombol satu-klik. Bagian yang sudah nyata & teruji ada
di sisi aplikasi (loader OpenBao + fallback env, lihat `settings/security.py`
dan `tests/test_config_secrets.py`). Bagian di folder ini adalah berkas
deployment yang perlu langkah operasional di bawah.

```
             :443/:80
  internet ───────────►  Caddy  ──► app (Streamlit/API) ──► Oracle / pgvector
             (TLS)               8501/8000        ▲
                                                  │ baca rahasia (sekali, cached)
                                               OpenBao  (KV v2: secret/txai12)
```

## Isi folder

| Berkas | Guna |
|---|---|
| `compose-infra.yaml` | OpenBao + Caddy + jaringan tersegmentasi |
| `Caddyfile` | Reverse proxy: TLS, header keamanan, catatan rate limit |
| `openbao/config.hcl` | OpenBao storage-file (persisten, bukan dev mode) |
| `openbao/txai12-policy.hcl` | Kebijakan **baca-saja** untuk token aplikasi |
| `openbao/bootstrap.sh` | Aktifkan KV, tulis rahasia, buat policy + token app |

## Cara kerja rahasia (env → OpenBao → default)

`settings/security.py` mengambil tiap kredensial dengan urutan:

1. **Environment** menang (untuk uji/darurat/override).
2. **OpenBao** — bila `OPENBAO_ADDR` + `OPENBAO_TOKEN` diset, rahasia dibaca
   dari `OPENBAO_KV_PATH` (default `secret/data/txai12`), sekali, lalu di-cache.
3. **Default lab** — hanya di luar produksi. Di `RAG_ENV=production`, rahasia
   yang tetap kosong **menggagalkan proses saat impor** (fail-closed).

Yang disetel lewat env hanyalah **alamat + token AKSES** ke OpenBao — bukan
kredensial DB itu sendiri. Rahasia sebenarnya hidup di dalam OpenBao. OpenBao
mati **tidak** mematikan app: ia jatuh ke langkah berikutnya (produksi tetap
fail-closed bila akhirnya kosong).

## Bootstrap (sekali)

Prasyarat: Docker berjalan; CLI `bao` (via container OpenBao) atau `curl`.

```sh
# 1) Nyalakan OpenBao + Caddy
docker compose -f infra/compose-infra.yaml up -d

# 2) Inisialisasi OpenBao — CATAT unseal keys + root token yang tercetak,
#    simpan TERPISAH & aman (mis. bagi 5 kunci ke 5 pemegang).
docker compose -f infra/compose-infra.yaml exec openbao \
  bao operator init -key-shares=5 -key-threshold=3

# 3) UNSEAL (ulangi dengan 3 unseal key berbeda)
docker compose -f infra/compose-infra.yaml exec openbao bao operator unseal <KEY_1>
docker compose -f infra/compose-infra.yaml exec openbao bao operator unseal <KEY_2>
docker compose -f infra/compose-infra.yaml exec openbao bao operator unseal <KEY_3>

# 4) Isi rahasia + buat token app. GANTI nilai 'GANTI' di bootstrap.sh dulu!
docker compose -f infra/compose-infra.yaml exec \
  -e OPENBAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=<ROOT_TOKEN> \
  openbao sh /openbao/bootstrap.sh
```

Perintah terakhir mencetak **OPENBAO_TOKEN** untuk aplikasi. Setel di
lingkungan app (bukan `.env` plaintext untuk produksi — idealnya via systemd
`EnvironmentFile` bermode 600, atau injektor rahasia):

```sh
export RAG_ENV=production
export OPENBAO_ADDR=http://127.0.0.1:8200
export OPENBAO_TOKEN=<token dari bootstrap>
export OPENBAO_KV_PATH=secret/data/txai12
# lalu jalankan app seperti biasa
```

Verifikasi tanpa menjalankan app penuh:

```sh
RAG_ENV=production OPENBAO_ADDR=http://127.0.0.1:8200 OPENBAO_TOKEN=<token> \
  python -c "from ragcore import config; print('OK', config.PG_URL_APP.rsplit('@',1)[-1])"
```

## Konsekuensi operasional (baca ini)

- **Seal/unseal.** Setiap restart container OpenBao → **tersegel** → app tak
  dapat rahasia sampai operator unseal dengan ambang kunci. Untuk single-node
  tanpa jaga, pertimbangkan **auto-unseal** (transit/cloud KMS). Ini
  konsekuensi desain OpenBao, bukan bug.
- **Rate limiting** di `Caddyfile` butuh plugin `caddy-ratelimit` (build
  xcaddy) atau ditegakkan di layer lain / di aplikasi. Contohnya disertakan,
  dikomentari.
- **TLS.** `.localhost` memakai CA internal Caddy (uji). Untuk publik, ganti ke
  domain sungguhan + buka email admin di blok global `Caddyfile` (Let's Encrypt).
- **App masih di host.** Compose ini menjalankan OpenBao + Caddy; aplikasi masih
  via venv di host, dijangkau Caddy lewat `host.docker.internal`. Untuk isolasi
  penuh (app di jaringan `backend` internal, port 8200 ditutup), app perlu
  dikontainerkan — termasuk SQLcl/Java untuk MCP Oracle — itu langkah terpisah.

## Langkah lanjut (belum di kerangka ini)

- **Dynamic secrets** OpenBao untuk `rag_baca`/`rag_app`: OpenBao membuat
  kredensial DB berumur pendek on-demand alih-alih rahasia statis. Kandidat
  paling kuat karena menghapus sandi DB jangka-panjang sepenuhnya.
- **AppRole** ketimbang token statis untuk identitas app (role_id + secret_id,
  rotasi otomatis).
- Dockerfile aplikasi + orkestrasi, agar seluruh jalur berjalan tersegmentasi.
