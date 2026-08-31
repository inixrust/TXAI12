#!/usr/bin/env sh
# Bootstrap OpenBao untuk TX-AI12 - jalankan SEKALI setelah `bao operator init`
# dan OpenBao sudah di-UNSEAL. Idempoten: aman diulang.
#
# Butuh env:
#   OPENBAO_ADDR  alamat OpenBao (mis. http://127.0.0.1:8200)
#   BAO_TOKEN     token root/admin dari `bao operator init`
#
# CLI `bao` memakai nama env Vault (VAULT_*) karena API-compatible.
set -eu

export VAULT_ADDR="${OPENBAO_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${BAO_TOKEN:?set BAO_TOKEN ke token admin dari 'bao operator init'}"

here="$(dirname "$0")"

# 1) Aktifkan KV v2 di path 'secret' (abaikan bila sudah ada).
bao secrets enable -path=secret kv-v2 2>/dev/null || true

# 2) Tulis rahasia TX-AI12. GANTI setiap 'GANTI' dengan kredensial SUNGGUHAN
#    sebelum produksi - nilai di sini hanya menunjukkan BENTUKnya. Nama kunci
#    HARUS sama persis dengan yang dibaca aplikasi (lihat settings/security.py
#    dan settings/database.py, settings/mcp.py).
bao kv put secret/txai12 \
  PG_URL="postgresql+psycopg://rag:GANTI@pg-txai12:5432/korpus" \
  PG_URL_DIRECT="postgresql://rag:GANTI@pg-txai12:5432/korpus" \
  PG_URL_APP="postgresql+psycopg://rag_app:GANTI@pg-txai12:5432/korpus" \
  ORACLE_CONNECTION="rag_baca/GANTI@oracle-txai12:1521/FREEPDB1" \
  ORACLE_CONNECTION_OPERATOR="rag_operator/GANTI@oracle-txai12:1521/FREEPDB1" \
  SESSION_SECRET="$(head -c 32 /dev/urandom | base64)"

# 3) Kebijakan baca-saja untuk aplikasi.
bao policy write txai12-read "$here/txai12-policy.hcl"

# 4) Token app berumur pendek dengan kebijakan itu. Nilai yang tercetak adalah
#    yang disetel sebagai OPENBAO_TOKEN di lingkungan aplikasi. TTL pendek +
#    period=1h berarti bisa diperbarui otomatis selama app hidup, tapi mati
#    tak lama setelah app berhenti - mengurangi dampak bila token bocor.
echo
echo "OPENBAO_TOKEN untuk aplikasi (setel di environment app):"
bao token create -policy=txai12-read -ttl=1h -period=1h -field=token
echo
echo "Selesai. Verifikasi: bao kv get secret/txai12"
