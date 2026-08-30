"""Ekstraksi dokumen pindaian dengan VLM (L3).

    python -m ragcore.commands.extract                    # seluruh korpus pindaian
    python -m ragcore.commands.extract scanned_documents/SOP-01-*.pdf
    python -m ragcore.commands.extract --ulang            # abaikan singgahan
"""
from __future__ import annotations

import sys
from pathlib import Path

from ragcore import config
from ragcore.extraction import vlm


def scan_file(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args if not a.startswith("--")]
    return sorted(config.SCAN_DOCUMENT.glob("*.pdf"))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    again = "--ulang" in argv

    file = scan_file(argv)
    if not file:
        print(f"Tidak ada PDF di {config.SCAN_DOCUMENT}")
        return 1

    print(f"  model vision : {config.MODEL_VISION}")
    print(f"  resolusi     : {config.DPI_RENDER} dpi")
    print(f"  singgahan    : {'diabaikan (--ulang)' if again else 'dipakai bila ada'}")
    print()

    page_total = total_vlm = 0
    for b in file:
        if not b.exists():
            print(f"  ! {b} tidak ada, dilewati")
            continue
        page = vlm.load_pdf_smart(b, use_cache=not again)
        dari_vlm = sum(h.metadata.get("ekstraksi") == "vlm" for h in page)
        page_total += len(page)
        total_vlm += dari_vlm

    print(f"\n  {total_vlm} dari {page_total} halaman lewat VLM.")
    print(f"  Hasilnya tersimpan sebagai berkas *{config.CACHE_SUFFIX} —")
    print("  pengindeksan ulang tidak akan memanggil VLM lagi.")
    print("\n  Berikutnya:  python -m ragcore.commands.quality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
