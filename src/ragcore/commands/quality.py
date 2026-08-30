"""Pemeriksaan mutu hasil ekstraksi, tiga lapis (L4).

    python -m ragcore.commands.quality                 # seluruh korpus pindaian
    python -m ragcore.commands.quality --tanpa-ocr     # lewati lapis 2

Lapis 2 menjalankan OCR pada halaman yang sama untuk dibandingkan angkanya.
Bila pytesseract tidak terpasang, lapis itu dilewati sendiri dan lapis 1
tetap berjalan — laporan tetap berguna, hanya lebih sedikit sinyalnya.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ragcore import config
from ragcore.extraction import quality, vlm


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    use_ocr = "--tanpa-ocr" not in argv

    file = [Path(a) for a in argv if not a.startswith("--")]
    if not file:
        file = sorted(config.SCAN_DOCUMENT.glob("*.pdf"))

    ada_yang_diperiksa = False
    for b in file:
        stored = vlm.read_cache(b)
        if not stored:
            print(f"  {b.name}: belum ada hasil ekstraksi. "
                  f"Jalankan dulu commands.extract")
            continue

        ada_yang_diperiksa = True
        print(f"\n  === {b.name} ===")

        ocr_page = {}
        if use_ocr:
            for no in stored:
                text = quality.extract_with_ocr(b, no)
                if text.strip():
                    ocr_page[no] = text
            if not ocr_page:
                print("  (lapis 2 dilewati: OCR tidak tersedia — "
                      "pasang pytesseract + data bahasa 'ind')")

        quality.quality_report(stored, ocr_page or None)

    if not ada_yang_diperiksa:
        return 1

    print("\n  Lapis 3 adalah Anda: buka halaman aslinya untuk nomor yang")
    print("  ditandai di atas, bandingkan, lalu ubah penandanya menjadi")
    print("  'terverifikasi' bila memang benar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
