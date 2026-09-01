#!/usr/bin/env sh
# Snapshot OpenBao (integrated storage / raft) -> berkas backup yang KONSISTEN
# dan bisa dipulihkan. Snapshot berisi SELURUH state terenkripsi; untuk
# memulihkannya tetap butuh unseal key yang sama - jadi simpan snapshot DAN
# unseal key di tempat TERPISAH.
#
# Jalankan DI DALAM container openbao (punya CLI `bao`), mis:
#   docker compose -f infra/compose-infra.yaml exec \
#     -e BAO_TOKEN=<token-snapshot> openbao sh /openbao/infra/backup.sh
#
# Butuh env:
#   OPENBAO_ADDR  default http://127.0.0.1:8200
#   BAO_TOKEN     token dengan kapabilitas 'read' pada sys/storage/raft/snapshot
#                 (root saat bootstrap; di produksi buat policy khusus backup)
set -eu

export VAULT_ADDR="${OPENBAO_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${BAO_TOKEN:?set BAO_TOKEN ke token dengan hak snapshot}"

stamp="$(date +%Y%m%d-%H%M%S)"
dir="/openbao/data/backups"
mkdir -p "$dir"
out="$dir/openbao-${stamp}.snap"

bao operator raft snapshot save "$out"
echo "snapshot tersimpan: $out ($(wc -c < "$out") byte)"
echo "Salin ke luar host & simpan aman:"
echo "  docker cp txai12-infra-openbao-1:$out ./"
echo
echo "PULIHKAN (di node kosong, MENIMPA state - hati-hati):"
echo "  bao operator raft snapshot restore <berkas.snap>"
