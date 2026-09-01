#!/usr/bin/env sh
# Konfigurasi KREDENSIAL DB DINAMIS (efemeral) untuk pgvector di OpenBao -
# menggantikan sandi DB statis dengan user+sandi berumur pendek yang diterbitkan
# per-permintaan. Peran dinamis dibuat sebagai ANGGOTA rag_app, jadi RLS tetap
# berlaku (kredensial dinamis pun hanya melihat baris unit pemohon).
#
# Jalankan SEKALI setelah OpenBao di-unseal. Butuh BAO_TOKEN admin.
#
# PRASYARAT JARINGAN: OpenBao harus bisa menjangkau pg-txai12 -
#   docker network connect txai12-net txai12-infra-openbao-1
set -eu

export VAULT_ADDR="${OPENBAO_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${BAO_TOKEN:?set BAO_TOKEN ke token admin}"

bao secrets enable database 2>/dev/null || true

# Koneksi admin ke Postgres (bisa CREATE ROLE). GANTI kredensial untuk produksi;
# idealnya user khusus-Vault, bukan pemilik data.
bao write database/config/pgvector \
  plugin_name=postgresql-database-plugin \
  allowed_roles=rag_app_dyn \
  connection_url='postgresql://{{username}}:{{password}}@pg-txai12:5432/korpus?sslmode=disable' \
  username="${PG_ADMIN_USER:-rag}" password="${PG_ADMIN_PASS:-rahasia_lab}"

# Peran dinamis: user efemeral, ANGGOTA rag_app -> RLS tetap. TTL 1 jam.
bao write database/roles/rag_app_dyn \
  db_name=pgvector default_ttl=1h max_ttl=4h \
  creation_statements="CREATE ROLE \"{{name}}\" LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' IN ROLE rag_app;" \
  revocation_statements="DROP ROLE IF EXISTS \"{{name}}\";"

echo "Selesai."
echo "  Uji terbitkan: bao read database/creds/rag_app_dyn"
echo "  App memakainya: setel OPENBAO_DB_ROLE=rag_app_dyn (policy sudah mengizinkan"
echo "  path database/creds/rag_app_dyn - lihat txai12-policy.hcl)."
