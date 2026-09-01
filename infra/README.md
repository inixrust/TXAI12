# Infra produksi TX-AI12 (kerangka)

Kerangka pengerasan untuk menjalankan TX-AI12 di luar lab: **manajemen rahasia
(OpenBao)** menggantikan rahasia plaintext di `.env`, dan **satu pintu masuk
ber-TLS (Caddy)** di depan aplikasi.

**Struktur:** seluruh DEPLOYMENT ada di folder ini (`infra/`) — compose DB
(`compose-oracle.yaml`, `compose-pgvector.yaml`), stack (`compose-infra.yaml`),
`Dockerfile`, `openbao/`, `Caddyfile`, dan SQL Oracle (`oracle/`). KODE aplikasi
ada di akar (`src/`, `apps/`). `compose.yaml` di akar meng-`include` ketiga
compose sebagai SATU project `txai12`:

```sh
docker network create txai12-net     # sekali - jaringan bersama app<->DB
docker compose up -d                 # seluruh stack (Oracle+pgvector+OpenBao+Caddy+app)
```

Tiap bagian tetap bisa dijalankan sendiri dengan `-f infra/<berkas>` (lihat
komentar di tiap compose). Stack Langfuse dikelola terpisah.

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

> **Sudah diuji langsung di Docker.** OpenBao (raft) di-init + unseal, rahasia
> lab ditulis ke `secret/txai12`, token app baca-saja dibuat, lalu aplikasi
> dijalankan `RAG_ENV=production` **tanpa satu pun kredensial DB di env** — dan
> berhasil: login (SESSION_SECRET dari OpenBao), koneksi pgvector + RLS (TI
> melihat 43 chunk, unit lain 30), sampai jawaban RAG ter-render di UI. Token
> salah → gagal-tertutup seperti seharusnya.

## Isi folder

| Berkas | Guna |
|---|---|
| `compose-infra.yaml` | OpenBao + Caddy + **app** + jaringan tersegmentasi |
| `Dockerfile` | Image aplikasi (Streamlit + ragcore + Java/SQLcl) |
| `Caddyfile` | Reverse proxy: TLS, header keamanan, catatan rate limit |
| `openbao/config.hcl` | OpenBao storage-raft (persisten, bukan dev mode) |
| `openbao/txai12-policy.hcl` | Kebijakan **baca-saja** untuk token aplikasi |
| `openbao/bootstrap.sh` | Aktifkan KV, tulis rahasia, buat policy + token app |
| `openbao/backup.sh` | Snapshot raft OpenBao (backup) |
| `scan.sh` | Pindai kerentanan image (Trivy) |

## Aplikasi dikontainerkan (menghapus lompatan ke host)

Awalnya app berjalan di HOST via venv, dan Caddy menjangkaunya lewat
`host.docker.internal` — yang di Docker Desktop terganjal Windows Firewall.
Kini app punya **image sendiri** (`infra/Dockerfile`) dan menjadi service `app`,
jadi **Caddy→app dan app→OpenBao/DB semuanya container→container** — tanpa
lompatan ke host, tanpa ganjalan firewall.

```sh
# 1) Bangun image (Streamlit + ragcore + Java/SQLcl; optional berat dilewati)
docker build -f infra/Dockerfile -t txai12-app:latest .

# 2) Jaringan bersama supaya app menjangkau DB dengan NAMA container
docker network create txai12-net
docker network connect txai12-net oracle-txai12
docker network connect txai12-net pg-txai12

# 3) Rahasia VARIAN CONTAINER: alamat DB pakai nama container (pg-txai12:5432,
#    oracle-txai12:1521), BUKAN localhost. Tulis ke path terpisah:
#      bao kv put secret/txai12-app PG_URL=...@pg-txai12:5432/... ORACLE_...=@oracle-txai12:1521/...
#    (kebijakan txai12-read sudah mengizinkan path txai12-app)

# 4) Jalankan seluruh stack (token app dari bootstrap)
OPENBAO_TOKEN=<token> CADDY_HTTPS_PORT=8443 CADDY_HTTP_PORT=8080 \
  docker compose -f infra/compose-infra.yaml up -d
```

**Sudah diuji end-to-end (container):** image 550 MB, app boot `RAG_ENV=production`
**tanpa kredensial DB di env** (semua dari OpenBao path `txai12-app`),
**Caddy TLS → app = HTTP 200** dengan header keamanan lengkap (HSTS/nosniff/
frame/referrer), pgvector RLS via `dbnet` (TI 43 chunk), login argon2id via
Oracle `dbnet`, dan Ollama di host terjangkau. Semua tanpa lompatan ke host.

> **Token OpenBao & masa berlaku.** App membaca rahasia SEKALI saat start lalu
> meng-cache. Token periodik yang tak diperbarui kedaluwarsa (mis. 1 jam) →
> **restart** container setelah itu gagal mengambil rahasia. Untuk lab, pakai
> `-period=24h`; solusi benar = AppRole + renew (endgame B).

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
#    (Berkas infra/ ter-mount di dalam container pada /openbao/infra.)
docker compose -f infra/compose-infra.yaml exec \
  -e OPENBAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=<ROOT_TOKEN> \
  openbao sh /openbao/infra/bootstrap.sh
```

Volume data di-chown otomatis oleh service `openbao-init` sebelum OpenBao start,
jadi tak perlu langkah manual. Backend penyimpanan adalah **raft** (integrated
storage) - persisten dan tidak usang.

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

- **Seal/unseal → AUTO-UNSEAL (sudah ada).** OpenBao tersegel tiap restart.
  Sidecar `openbao-autounseal` memantau dan meng-unseal otomatis dari berkas
  kunci `infra/openbao/unseal-keys.txt` (**di-gitignore**, salin dari
  `unseal-keys.txt.example`). Diuji: restart OpenBao → tersegel → sidecar
  meng-unseal < 16 detik, tanpa campur tangan. **Trade-off:** kunci ada di
  berkas (lindungi 0600) — ini SUBSTITUSI LAB untuk auto-unseal KMS/transit yang
  tak ada di on-prem single-node. Produksi: pakai transit/KMS.
- **Rate limiting** di `Caddyfile` butuh plugin `caddy-ratelimit` (build
  xcaddy) atau ditegakkan di layer lain / di aplikasi. Contohnya disertakan,
  dikomentari.
- **TLS.** `.localhost` memakai CA internal Caddy (uji). Untuk publik, ganti ke
  domain sungguhan + buka email admin di blok global `Caddyfile` (Let's Encrypt).
  Diuji langsung: Caddy naik, menerbitkan sertifikat internal untuk
  `tx-ai12.localhost`, dan **terminasi TLS berhasil** (handshake + `Server:
  Caddy`). Header keamanan (HSTS/nosniff/frame/referrer) terpasang di config dan
  dikirim pada respons sukses.
- **Port 80/443 sudah dipakai?** Di Docker Desktop, ingress k8s bawaan sering
  memegang 80/443 sehingga Caddy gagal mem-publish diam-diam. Timpa port host:
  `CADDY_HTTP_PORT=8080 CADDY_HTTPS_PORT=8443 docker compose -f
  infra/compose-infra.yaml up -d caddy`.
- **Caddy → app (SUDAH DIKONTAINERKAN).** Dulu Caddy menjangkau app di host
  lewat `host.docker.internal`, yang terganjal Windows Firewall (container→host).
  Kini app adalah container: Caddy → `app:8501` container→container, terbukti
  **HTTP 200** + header keamanan. Bila sengaja menjalankan app di host, timpa
  target: `APP_UPSTREAM=host.docker.internal:8501` (dan sadari batas firewall).
- **Ollama.** App menjangkau Ollama di host lewat `host.docker.internal:11434`
  (di mesin uji ini terjangkau — Ollama membuka port-nya sendiri). Bila
  firewall memblokirnya, jalankan Ollama sebagai container atau tambah aturan
  inbound. Timpa `OLLAMA_BASE_URL` sesuai lingkungan.
- **Isolasi jaringan penuh kini mungkin.** Karena app+OpenBao+DB semua di dalam
  Docker, `backend` boleh dijadikan `internal: true` dan port 8200 ditutup
  begitu host app pensiun — lihat komentar di `compose-infra.yaml`.

## Backup, hardening & pemindaian (sudah dikerjakan)

- **Backup OpenBao (snapshot raft).** [openbao/backup.sh](openbao/backup.sh)
  mengambil snapshot state penuh (terenkripsi). Jalankan berkala + salin keluar:
  ```sh
  docker compose -f infra/compose-infra.yaml exec \
    -e BAO_TOKEN=<token-snapshot> openbao sh /openbao/infra/backup.sh
  docker cp txai12-infra-openbao-1:/openbao/data/backups/<file>.snap ./
  ```
  Pulihkan di node kosong: `bao operator raft snapshot restore <file>.snap`.
  Snapshot butuh unseal key yang SAMA untuk dibuka - simpan snapshot & key
  TERPISAH. Diuji: snapshot valid (gzip) ~21 KB.
- **Hardening container.** OpenBao & Caddy kini: `no-new-privileges`, batas
  memori/CPU (`mem_limit`/`cpus`), dan healthcheck OpenBao (`bao status` →
  unhealthy saat tersegel, sinyal jujur). `restart: unless-stopped`.
- **Pemindaian image (Trivy).** [scan.sh](scan.sh) memindai tanpa instalasi:
  ```sh
  sh infra/scan.sh
  ```
  Temuan saat ditulis (keduanya di runtime Go bawaan image, BUKAN config kita):
  `CVE-2026-56854` (`golang.org/x/crypto`, CRITICAL) di caddy:2 & openbao —
  perbaikannya di hulu (x/crypto ≥ 0.55.0). Pantau rilis image; pin digest yang
  sudah ditambal saat tersedia. Selain itu beberapa HIGH tingkat OS/alpine.

## AppRole & kredensial DB dinamis (sudah dikerjakan)

**AppRole — identitas app tanpa token statis.** App tak lagi memakai
`OPENBAO_TOKEN` yang bisa kedaluwarsa. Ia LOGIN SEGAR tiap start dengan
`OPENBAO_ROLE_ID` + `OPENBAO_SECRET_ID` (berumur panjang) dan mendapat token
pendek untuk sesi itu (`settings/security.py:_approle_login`). Inilah yang
menyelesaikan masalah "token 1 jam mati → restart gagal".

```sh
bao auth enable approle
bao write auth/approle/role/txai12 token_policies=txai12-read token_ttl=1h token_max_ttl=4h
bao read  auth/approle/role/txai12/role-id            # -> OPENBAO_ROLE_ID
bao write -f auth/approle/role/txai12/secret-id       # -> OPENBAO_SECRET_ID
# lalu: OPENBAO_ROLE_ID=... OPENBAO_SECRET_ID=... docker compose ... up -d app
```

**Dynamic secrets — sandi DB efemeral, RLS tetap.** [openbao/dynamic-db.sh](openbao/dynamic-db.sh)
mengonfigurasi secrets engine `database` untuk pgvector. Peran `rag_app_dyn`
menerbitkan user+sandi berumur pendek (TTL 1 jam) yang dibuat sebagai **ANGGOTA
`rag_app`** — sehingga **RLS tetap berlaku** pada kredensial dinamis. Aktifkan di
app dengan `OPENBAO_DB_ROLE=rag_app_dyn` (opt-in; `security.maybe_dynamic_db`).

Diuji end-to-end di container: app login AppRole (tanpa token statis) →
mengambil kredensial DB efemeral → `current_user` = `v-approle-rag_app_-…`
(bukan sandi statis) → RLS utuh (unit TI 43 chunk, lain 30). Tak ada sandi DB
jangka-panjang di mana pun.

**Lease renewal otomatis (batas jujur di atas — sudah ditutup).**
`security.start_lease_renewer` menjalankan thread latar yang MEMPERPANJANG lease
sebelum kedaluwarsa, dan MEROTASI ke kredensial baru saat mendekati max_ttl
(`refresh_dynamic_db`: renew → rotate). Dipanggil sekali dari `apps/app12.py`
(aman terhadap rerun Streamlit). Jadi proses berumur panjang tak lagi putus.

## Langkah lanjut (belum di kerangka ini)

- **Auto-unseal via transit/KMS** menggantikan berkas kunci lab (menghapus
  penyimpanan kunci unseal di disk).
- **Keycloak/OIDC (endgame B)** menggantikan login sandi app sepenuhnya.
