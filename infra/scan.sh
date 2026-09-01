#!/usr/bin/env sh
# Pindai kerentanan image infra dengan Trivy - TANPA instalasi, lewat container.
#
#   sh infra/scan.sh                 # HIGH+CRITICAL untuk caddy + openbao
#   SEV=CRITICAL sh infra/scan.sh    # hanya CRITICAL
#
# Cache DB kerentanan disimpan di volume 'trivy-cache' supaya jalan kedua cepat.
set -eu

SEV="${SEV:-HIGH,CRITICAL}"
IMAGES="${IMAGES:-caddy:2 openbao/openbao:latest}"

for img in $IMAGES; do
  echo "======================= $img ($SEV) ======================="
  docker run --rm -v trivy-cache:/root/.cache aquasec/trivy:latest \
    image --scanners vuln --severity "$SEV" --no-progress "$img"
done
