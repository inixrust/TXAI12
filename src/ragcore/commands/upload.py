"""python -m ragcore.commands.upload — masukkan berkas ke queue ingest.

    python -m ragcore.commands.upload dokumen.pdf
    python -m ragcore.commands.upload dokumen.pdf --jenis edaran
    python -m ragcore.commands.upload dokumen.pdf --unit "Divisi TI"
    python -m ragcore.commands.upload --status        lihat queue

Klasifikasi bawaannya `terbatas`, bukan `umum`: jalur unggah GAGAL TERTUTUP.
Lihat alasannya di ingest/queue.kirim().

Perintah ini SENGAJA tidak mengindeks apa pun. Ia menyimpan berkas dan
menaruh satu tugas di queue, lalu selesai - biasanya dalam sepersekian
detik. Yang mengindeks adalah pekerja:

    python -m ragcore.commands.worker

Pemisahan itulah inti modulnya. Pengguna yang mengunggah dokumen tidak
boleh menunggu ekstraksi VLM selesai; di lab ini satu halaman saja memakan
sekitar dua menit.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..ingest import blob, queue


def _status() -> int:
    summarize = queue.summarize()
    if not summarize:
        print("  Antrean kosong.")
        return 0
    print("  " + "  ".join(f"{s}={n}" for s, n in sorted(summarize.items())))
    print()
    print(f"  {'id':>4} {'status':10} {'ptg':>4} {'berkas':34} pesan")
    for t in queue.listing():
        message = (t["pesan"] or "")[:36]
        print(f"  {t['id']:>4} {t['status']:10} "
              f"{t['potongan'] or '-'!s:>4} {t['nama_berkas'][:34]:34} {message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--status" in argv:
        return _status()

    def _get(name: str, default: str | None) -> str | None:
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                value = argv[i + 1]
                del argv[i:i + 2]
                return value
        return default

    kind = _get("--jenis", "sop")
    unit = _get("--unit", None)
    classification = _get("--klasifikasi", "terbatas")

    file = [a for a in argv if not a.startswith("--")]
    if not file:
        print(__doc__)
        return 1

    for b in file:
        origin = Path(b)
        if not origin.exists():
            print(f"  TIDAK ADA: {origin}")
            return 1
        try:
            name, file_path = blob.save(origin.name, origin.read_bytes())
        except blob.TooLarge as e:
            print(f"  DITOLAK: {origin.name} - {e}")
            return 1
        task_id = queue.send(name, str(file_path), kind,
                                 unit=unit, classification=classification)
        print(f"  [{task_id}] {name} masuk antrean "
              f"(jenis={kind}, unit={unit or '-'}, {classification})")

    print("  Jalankan pekerja untuk memprosesnya:")
    print("    python -m ragcore.commands.worker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
