"""Kelola hash sandi per-user di ncs.pengguna_auth (argon2id).

    python -m ragcore.commands.auth --seed          # semua user REGISTRY, sandi default
    python -m ragcore.commands.auth --set NCS-0001  # setel sandi satu user (ditanya)
    python -m ragcore.commands.auth --daftar        # lihat NIP yang punya sandi

MENULIS ke ncs.pengguna_auth -> butuh koneksi PEMILIK (ncs), BUKAN rag_auth yang
hanya baca. Ambil dari ORACLE_CONNECTION_ADMIN, atau default pemilik lab.

Seed default memakai sandi 'lab2026' agar lab tetap jalan tanpa friksi - TETAPI
kini tiap user punya hash argon2id SENDIRI (salt sendiri), dan sandinya bisa
diganti per-user tanpa memengaruhi yang lain. Di produksi: beri tiap orang sandi
berbeda (mis. `--set` satu per satu), atau pindah ke IdP (endgame B).
"""
from __future__ import annotations

import argparse
import getpass
import os

from ragcore.domain import auth
from ragcore.domain.users import REGISTRY

# Pemilik tabel (bisa MENULIS). Default = kredensial pemilik lab; timpa lewat env
# untuk produksi. rag_auth TIDAK dipakai di sini - ia hanya-baca.
_ADMIN = os.getenv(
    "ORACLE_CONNECTION_ADMIN",
    "ncs/Rahasia_Lab_2026@localhost:1521/FREEPDB1",
)

_SEED_PASSWORD = os.getenv("LAB_SEED_PASSWORD", "lab2026")


def _upsert(conn, nip: str, password: str) -> None:
    """MERGE hash argon2id untuk satu NIP. Idempoten."""
    cur = conn.cursor()
    cur.execute(
        """
        MERGE INTO ncs.pengguna_auth d
        USING (SELECT :nip AS nip FROM dual) s ON (d.nip = s.nip)
        WHEN MATCHED THEN
          UPDATE SET hash_sandi = :h, algo = 'argon2id', diperbarui = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
          INSERT (nip, hash_sandi, algo) VALUES (:nip, :h, 'argon2id')
        """,
        {"nip": nip, "h": auth.hash_password(password)},
    )
    conn.commit()


def _seed() -> None:
    with auth._connect(_ADMIN) as conn:
        for nip in REGISTRY:
            _upsert(conn, nip, _SEED_PASSWORD)
    print(f"Seed {len(REGISTRY)} user dengan sandi default "
          f"(argon2id, hash per-user). Ganti per-user dengan --set.")


def _set(nip: str) -> None:
    nip = nip.strip().upper()
    p1 = getpass.getpass(f"Sandi baru untuk {nip}: ")
    if not p1 or p1 != getpass.getpass("Ulangi: "):
        raise SystemExit("Sandi kosong atau tak cocok - dibatalkan.")
    with auth._connect(_ADMIN) as conn:
        _upsert(conn, nip, p1)
    print(f"Sandi {nip} diperbarui (argon2id).")


def _daftar() -> None:
    with auth._connect(_ADMIN) as conn:
        cur = conn.cursor()
        cur.execute("SELECT nip, algo, diperbarui FROM ncs.pengguna_auth ORDER BY nip")
        for nip, algo, kapan in cur.fetchall():
            print(f"  {nip}  {algo}  {kapan:%Y-%m-%d %H:%M}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Kelola hash sandi per-user (argon2id).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--seed", action="store_true",
                   help="isi sandi default untuk semua user REGISTRY")
    g.add_argument("--set", metavar="NIP", help="setel sandi satu user (ditanya)")
    g.add_argument("--daftar", action="store_true", help="daftar NIP yang punya sandi")
    args = ap.parse_args()
    if args.seed:
        _seed()
    elif args.set:
        _set(args.set)
    else:
        _daftar()


if __name__ == "__main__":
    main()
