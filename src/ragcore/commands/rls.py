"""Peragaan Row-Level Security di pgvector (L6).

    python -m ragcore.commands.rls --pasang        # buat peran + kebijakan
    python -m ragcore.commands.rls --peragakan     # dua unit, dua jumlah baris
    python -m ragcore.commands.rls --retrieval   # RLS menahan hasil pencarian

Peragaannya yang menutup perdebatan, bukan penjelasannya: pertanyaan yang
sama, dua users, dua jumlah baris.
"""
from __future__ import annotations

import sys

from ragcore import config
from ragcore.domain import users as P
from ragcore.retrieval.retriever import search_vector
from ragcore.storage import pgvector


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--pasang" in argv:
        print("  Membuat peran aplikasi (non-pemilik, tunduk RLS)...")
        pgvector.create_app_role()
        print("  Memasang kebijakan lihat_sesuai_unit...")
        pgvector.install_rls()
        print("  Selesai. Jalankan --peragakan untuk membuktikannya.")
        return 0

    if "--peragakan" in argv:
        total = pgvector.vector_count()
        print(f"  Sebagai PEMILIK tabel      : {total} baris")
        print("  (pemilik tabel KEBAL RLS - inilah jebakan pertama)\n")
        for unit in ("Divisi SDM", "Divisi TI", "Divisi Umum"):
            try:
                n = pgvector.count_as(unit)
                print(f"  {config.GUC_UNIT}={unit:<14} -> {n} baris")
            except Exception as e:
                print(f"  {unit}: gagal ({type(e).__name__}: {e})")
        print("\n  Pertanyaan yang sama, jumlah baris berbeda. Pembatasan itu")
        print("  berlaku pada SETIAP query, termasuk yang lupa menyaring.")
        return 0

    if "--retrieval" in argv:
        return _demo_retrieval()

    print(__doc__)
    return 1


def _demo_retrieval() -> int:
    """Peragaan yang paling menentukan: RLS menahan PENGAMBILAN, bukan
    hanya COUNT.

    Penyaring aplikasi sengaja DIMATIKAN (filters={}). Kalau setelah itu
    seorang users masih tidak melihat dokumen unit lain, penyebabnya
    hanya satu: basis data yang menahannya.
    """

    query_text = "Apa aturan keamanan informasi dan kata sandi?"
    print(f"  Pertanyaan: {query_text}")
    print("  Menyasar SOP-05 — milik Divisi TI, berklasifikasi TERBATAS.")
    print("  Penyaring aplikasi DIMATIKAN; yang tersisa hanya RLS.\n")

    row = [(None, "TANPA LOGIN (pemilik tabel)")]
    row += [(P.REGISTRY[n], str(P.REGISTRY[n]))
              for n in ("NCS-0012", "NCS-0023", "NCS-0031")]

    for person, label in row:
        result = search_vector(query_text, filters={}, person=person)
        terbatas = sum(d.metadata.get("klasifikasi") == "terbatas" for d in result)
        marker = "  <- KEBAL RLS" if person is None else ""
        print(f"  {label:40} {len(result):2d} hasil, "
              f"{terbatas} terbatas{marker}")

    print("\n  Andini di Divisi SDM tidak melihat satu pun dokumen terbatas")
    print("  milik Divisi TI — padahal filters aplikasinya dimatikan.")
    print("  Itu penegakan, bukan penyaringan.")
    print("\n  Baris pertama adalah pengingatnya: aplikasi yang menyambung")
    print("  sebagai pemilik tabel melewati seluruh kebijakan tanpa peringatan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
