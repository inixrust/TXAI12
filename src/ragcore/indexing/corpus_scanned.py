"""Memuat korpus hasil pindaian ke dalam pipeline indexing (L3 -> L6).

Inilah sambungan yang membuat rantai empat hari itu nyata: keluaran ekstraksi
Hari 1 menjadi masukan indeks Hari 2, yang menjadi sumber jawaban Hari 3.

Bedanya dengan korpus.py biasa ada tiga:

  1. Halaman tanpa lapisan teks dialihkan ke VLM (atau dibaca dari singgahan).
  2. Pemotongannya sadar tabel — tabel tidak dipisahkan dari judul kolomnya.
  3. Metadata membawa penanda asal dan mutu, supaya bisa disaring di L6 dan
     dipakai memutuskan peninjauan manusia di L10.
"""
from __future__ import annotations

from ragcore.domain import Document

from .. import config
from ..extraction import quality as periksa_mutu
from ..extraction import vlm
from ..extraction.table_chunker import chunk_table_aware
from . import tagger

NAME_WIDTH = 44

# Jenis dokumen ditebak dari nama berkas. Korpus pindaian tidak punya struktur
# subfolder seperti documents/, jadi jenisnya diambil dari awalan nomornya.
KIND_PREFIX = {"SOP": "sop", "SE": "edaran", "NR": "notulen"}


def kind_from_name(name: str) -> str:
    for prefix, kind in KIND_PREFIX.items():
        if name.upper().startswith(prefix):
            return kind
    return "lain"


def original_name(scan_name: str) -> str:
    """'SOP-01-Kepegawaian-PINDAI.pdf' -> 'SOP-01-Kepegawaian.pdf'.

    Sitasi harus menunjuk nama dokumen yang dikenali orang, bukan nama berkas
    kerja kita. Peserta yang membaca '[dokumen: SOP-01-...-PINDAI.pdf]' akan
    mengira itu dokumen yang berbeda.
    """
    return scan_name.replace("-PINDAI.pdf", ".pdf")


def load_scan(quiet: bool = False,
                  cross_check: bool = False) -> list[Document]:
    """Muat seluruh PDF pindaian, ekstrak bila perlu, potong sadar tabel.

    periksa_silang=True menjalankan OCR pembanding untuk menandai mutu tiap
    halaman. Mahal, jadi bawaannya mati — mutu biasanya sudah diperiksa
    terpisah lewat commands.quality, dan hasilnya dibaca dari singgahan.
    """
    root = config.SCAN_DOCUMENT
    if not root.exists():
        return []

    everything: list[Document] = []
    for file in sorted(root.glob("*.pdf")):
        page = vlm.load_pdf_smart(file, quiet=quiet)
        kind = kind_from_name(file.name)
        original = original_name(file.name)

        # Mutu per halaman: dipakai menandai chunks, bukan menolaknya.
        # Potongan yang mencurigakan tetap masuk indeks — yang berubah adalah
        # peringatan yang menyertainya saat dipakai menjawab.
        review_pages: set[int] = set()
        for h in page:
            if h.metadata.get("ekstraksi") != "vlm":
                continue
            lapor = periksa_mutu.check_structural(h.page_content)
            if cross_check:
                ocr_text = periksa_mutu.extract_with_ocr(file, h.metadata["page"])
                if ocr_text.strip():
                    cross = periksa_mutu.cross_check(h.page_content, ocr_text)
                    if cross["perlu_diperiksa"]:
                        lapor["curiga"].append("angka tidak sepakat dengan OCR")
            if lapor["curiga"]:
                review_pages.add(h.metadata["page"])

        chunks: list[Document] = []
        for h in page:
            for section in chunk_table_aware(h.page_content):
                meta = dict(h.metadata)
                meta["source"] = original
                meta["berkas_pindaian"] = file.name
                meta["mutu_ekstraksi"] = (
                    "perlu_tinjau" if meta.get("page") in review_pages else "lolos")
                chunks.append(Document(page_content=section, metadata=meta))

        chunks = tagger.add_context(chunks, kind, original)
        everything += chunks

        if not quiet:
            ditandai = sum(p.metadata.get("mutu_ekstraksi") == "perlu_tinjau"
                           for p in chunks)
            print(f"  {file.name:{NAME_WIDTH}s} {len(chunks):3d} potongan "
                  f"({len(review_pages)} halaman perlu tinjau, "
                  f"{ditandai} potongan ditandai)")

    return everything
