# Peta Akses TX-AI12 — apa yang bisa diakses & caranya

Semua komponen berjalan di Docker sebagai dua project: **`txai12`** (app + DB +
OpenBao + Caddy) dan **`txai12-observer`** (Langfuse). Aturan umum:

- **UI web hanya lewat HTTPS di gerbang Caddy** (`*.localhost:8443`). Port HTTP
  mentah OpenBao (8200) & Langfuse (3000) SUDAH DITUTUP.
- `*.localhost` otomatis menunjuk `127.0.0.1` di browser modern (Chrome/Edge/
  Firefox). Untuk `curl`, pakai `--resolve <host>:8443:127.0.0.1 -k`.
- Port `8443` (bukan 443) karena 80/443 dipegang ingress k8s Docker Desktop.
- **CA internal Caddy** → browser menampilkan "Your connection is not private"
  → **Advanced → Proceed**. Hilangkan sekali dengan mempercayai root CA (lihat
  infra/README, bagian TLS).

---

## 1. Akses lewat WEB (browser) — via Caddy TLS

| Layanan | URL | Login |
|---|---|---|
| **Aplikasi TX-AI12** (Streamlit) | `https://tx-ai12.localhost:8443` | pilih NIP di dropdown + sandi **`lab2026`** (argon2id per-user di Oracle) |
| **Langfuse** (observability) | `https://langfuse.localhost:8443` | `instruktur@lab.local` / `lab2026lab2026` |
| **OpenBao** (secret manager) | `https://openbao.localhost:8443` → `/ui` | Method **Token**; tempel token (AppRole/root) |
| **minio console** (storage Langfuse) | `https://minio-console.localhost:8443` | `minio` / `miniosecret` |
| **minio S3 API** (media Langfuse) | `https://minio.localhost:8443` | dipakai otomatis oleh URL presigned Langfuse |

> Semua di atas lewat Caddy TLS (`:8443`). Tak ada lagi UI/API via HTTP mentah.
> Mengelola stack: `txai12` dari `docker compose` di akar; `txai12-observer`
> (Langfuse) dari `docker compose -f infra/compose-observer.yaml`.

---

## 2. Akses lewat CLI / klien

### Basis data
| DB | Alamat (host) | Akun | Cara |
|---|---|---|---|
| **Oracle** (data terstruktur) | `localhost:1521/FREEPDB1` | `system`, `ncs`, `rag_baca`, `rag_operator`, `rag_auth` — sandi `Rahasia_Lab_2026` | `sql <user>/<pw>@localhost:1521/FREEPDB1` (SQLcl) atau `docker exec -it oracle-txai12 sqlplus <user>/<pw>@localhost/FREEPDB1` |
| **pgvector** (indeks + checkpointer) | `localhost:6024/korpus` | `rag`/`rahasia_lab` (pemilik), `rag_app`/`rahasia_app` (peran RLS) | `psql "postgresql://rag:rahasia_lab@localhost:6024/korpus"` atau `docker exec -it pg-txai12 psql -U rag -d korpus` |

Peran Oracle & maknanya: `ncs` (pemilik data), `rag_baca` (query hanya-baca,
hak-minimal), `rag_operator` (lihat-semua terkontrol), `rag_auth` (hanya baca
hash sandi + identitas). Di pgvector, `rag_app` tunduk RLS per-unit; `rag`
pemilik (kebal RLS, hanya untuk indexing/maintenance).

### Secret manager (OpenBao) — port 8200 host DITUTUP
```sh
docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=<token> \
  txai12-openbao-1 bao <perintah>            # mis. kv get secret/txai12-app
# atau via HTTPS: curl -k https://openbao.localhost:8443/v1/... -H "X-Vault-Token: <token>"
```

### Aplikasi (CLI) — di host, dalam venv
```sh
python -m ragcore.commands.index      # bangun/refresh indeks korpus
python -m ragcore.commands.rls        # pasang/uji Row-Level Security
python -m ragcore.commands.mcp        # kelola sambungan MCP Oracle
python -m ragcore.commands.auth --seed / --set <NIP> / --daftar   # hash sandi user
python -m ragcore.commands.evaluate_hybrid   # evaluasi agen hibrida
```

### DB internal Langfuse (JANGAN dipakai langsung — milik Langfuse)
Semua **localhost-only**: Postgres `127.0.0.1:5432`, ClickHouse `127.0.0.1:8123`
(HTTP) / `9000` (native), Redis `127.0.0.1:6379`. minio TIDAK lagi punya port
HTTP host — hanya via Caddy TLS (`minio.localhost` / `minio-console.localhost`)
dan internal (`minio:9000`). Ini penyimpanan internal Langfuse; akses lewat UI.

---

## 3. Yang TIDAK menghadap host (hanya jaringan Docker)
- **Aplikasi (Streamlit)** `8501` — hanya lewat Caddy (`tx-ai12.localhost`).
- **OpenBao** `8200`, **Langfuse web** `3000` — hanya lewat Caddy + internal.
- Komunikasi antar-container (app→openbao, app→DB, Caddy→layanan) di jaringan
  Docker terinternal (`txai12_frontend/backend/dbnet`, `txai12-observer_default`).

## 4. Ringkasan sandi lab (GANTI untuk produksi)
| Untuk | Nilai lab |
|---|---|
| Login aplikasi (semua NIP) | `lab2026` |
| Oracle (semua akun) | `Rahasia_Lab_2026` |
| pgvector | `rahasia_lab` (rag), `rahasia_app` (rag_app) |
| Langfuse UI | `instruktur@lab.local` / `lab2026lab2026` |
| minio | `minio` / `miniosecret` |
| OpenBao | berbasis token (AppRole/root), bukan sandi |
