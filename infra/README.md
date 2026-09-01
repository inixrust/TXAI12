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

> **Sudah diuji langsung di Docker.** OpenBao (raft) di-init + unseal, rahasia
> lab ditulis ke `secret/txai12`, token app baca-saja dibuat, lalu aplikasi
> dijalankan `RAG_ENV=production` **tanpa satu pun kredensial DB di env** — dan
> berhasil: login (SESSION_SECRET dari OpenBao), koneksi pgvector + RLS (TI
> melihat 43 chunk, unit lain 30), sampai jawaban RAG ter-render di UI. Token
> salah → gagal-tertutup seperti seharusnya.

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

- **Seal/unseal.** Setiap restart container OpenBao → **tersegel** → app tak
  dapat rahasia sampai operator unseal dengan ambang kunci. Untuk single-node
  tanpa jaga, pertimbangkan **auto-unseal** (transit/cloud KMS). Ini
  konsekuensi desain OpenBao, bukan bug.
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
- **Caddy → app di host (Docker Desktop).** Pakai `host.docker.internal` BAWAAN
  Docker Desktop (IPv4) — JANGAN menimpanya dengan `extra_hosts: host-gateway`,
  yang di sebagian versi resolve ke gateway IPv6 dan app (bind IPv4) tak
  mendengar → 502. Bahkan setelah resolve IPv4 benar, **Windows Defender
  Firewall memblokir koneksi container→host** secara bawaan, jadi Caddy tak bisa
  menjangkau Streamlit di host sampai ditambah aturan inbound untuk vEthernet
  Docker/WSL — ATAU (lebih baik, arah produksi) app dikontainerkan sehingga tak
  ada lompatan ke host sama sekali. TLS Caddy sendiri sudah terbukti; lompatan
  ke app inilah yang menunggu salah satu dari dua itu.
- **App masih di host → jaringan belum `internal`.** Compose ini menjalankan
  OpenBao + Caddy; aplikasi masih via venv di host, menjangkau OpenBao lewat
  port 8200 yang di-publish dan dijangkau Caddy lewat `host.docker.internal`.
  Karena `internal: true` memutus NAT (jaringan internal tak bisa mem-publish
  port), jaringan `backend` **sengaja belum internal**. Untuk isolasi penuh
  (OpenBao berhenti mem-publish 8200, app di `backend` internal), app perlu
  dikontainerkan — termasuk SQLcl/Java untuk MCP Oracle — lalu aktifkan
  `internal: true`. Itu langkah terpisah.

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

## Langkah lanjut (belum di kerangka ini)

- **Dynamic secrets** OpenBao untuk `rag_baca`/`rag_app`: OpenBao membuat
  kredensial DB berumur pendek on-demand alih-alih rahasia statis. Kandidat
  paling kuat karena menghapus sandi DB jangka-panjang sepenuhnya.
- **AppRole** ketimbang token statis untuk identitas app (role_id + secret_id,
  rotasi otomatis).
- Dockerfile aplikasi + orkestrasi, agar seluruh jalur berjalan tersegmentasi.
