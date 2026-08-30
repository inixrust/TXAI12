# -*- coding: utf-8 -*-
"""Membuat versi 'hasil pindaian' dari dokumen SOP yang sudah ada.

Kenapa dibuat, bukan diambil dari arsip nyata: dokumen kelas harus punya cacat
yang TERKENDALI. Kita perlu tahu persis halaman mana yang miring, mana yang
kurang cahaya, dan mana yang bertulisan tangan — supaya bisa membuktikan di
kelas bahwa alat deteksi bekerja pada cacat yang memang ada.

Keluaran: PDF berisi GAMBAR saja, tanpa lapisan teks sama sekali. Persis
seperti hasil pemindai kantor.

    python make_scans.py
"""
from __future__ import annotations

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

AKAR = Path(__file__).parent
ASAL = AKAR / "source_originals"   # bukan dokumen/: lihat config.ORIGINAL_SOURCE
TUJUAN = AKAR / "dokumen_pindaian"

DPI_PINDAI = 200          # DPI pemindai kantor pada umumnya
ACAK = random.Random(20260726)   # tetap: hasil sama di setiap mesin


# ---------------------------------------------------------------- cacat

def miringkan(gbr: Image.Image, derajat: float) -> Image.Image:
    """Kertas yang tidak lurus di atas kaca pemindai."""
    return gbr.rotate(derajat, resample=Image.BICUBIC,
                      expand=False, fillcolor=(248, 247, 244))


def kurangi_cahaya(gbr: Image.Image, terang: float, kontras: float) -> Image.Image:
    """Fotokopi generasi ketiga: pudar dan kontrasnya rendah."""
    gbr = ImageEnhance.Brightness(gbr).enhance(terang)
    return ImageEnhance.Contrast(gbr).enhance(kontras)


def beri_bintik(gbr: Image.Image, kepadatan: float = 0.0006) -> Image.Image:
    """Debu di kaca pemindai dan bintik toner."""
    lukis = ImageDraw.Draw(gbr)
    l, t = gbr.size
    for _ in range(int(l * t * kepadatan)):
        x, y = ACAK.randrange(l), ACAK.randrange(t)
        r = ACAK.choice([0, 0, 0, 1, 1, 2])
        abu = ACAK.randint(40, 150)
        lukis.ellipse([x - r, y - r, x + r, y + r], fill=(abu, abu, abu))
    return gbr


def garis_lipatan(gbr: Image.Image) -> Image.Image:
    """Bekas lipatan kertas — garis abu memanjang."""
    lukis = ImageDraw.Draw(gbr)
    l, t = gbr.size
    y = int(t * ACAK.uniform(0.42, 0.58))
    for d in (-1, 0, 1):
        abu = 205 if d else 185
        lukis.line([(0, y + d), (l, y + d + ACAK.randint(-3, 3))],
                   fill=(abu, abu, abu), width=1)
    return gbr


def tulisan_tangan(gbr: Image.Image, baris: list[str]) -> Image.Image:
    """Disposisi tulis tangan di tepi halaman.

    Digambar sebagai coretan, bukan huruf — inilah yang membedakan VLM dari
    OCR. OCR akan melewatkannya sama sekali; VLM setidaknya mengenali bahwa
    ADA tulisan tangan di sana, meski isinya bisa keliru dibaca.
    """
    lukis = ImageDraw.Draw(gbr)
    l, t = gbr.size
    x0, y0 = int(l * 0.58), int(t * 0.06)
    biru = (28, 42, 120)

    for i, teks in enumerate(baris):
        y = y0 + i * int(t * 0.028)
        x = x0
        for huruf in teks:
            if huruf == " ":
                x += int(l * 0.010)
                continue
            lebar = int(l * ACAK.uniform(0.006, 0.011))
            titik = [(x, y + ACAK.randint(-2, 2))]
            for k in range(1, 5):
                titik.append((x + lebar * k // 4,
                              y + ACAK.randint(-9, 9)))
            lukis.line(titik, fill=biru, width=2, joint="curve")
            x += lebar + int(l * 0.002)

    # paraf di bawah disposisi
    py = y0 + len(baris) * int(t * 0.028) + int(t * 0.02)
    px = x0 + int(l * 0.04)
    lukis.line([(px, py), (px + 40, py - 25), (px + 15, py + 10),
                (px + 70, py - 20), (px + 95, py + 5)],
               fill=biru, width=3, joint="curve")
    return gbr


# ---------------------------------------------------------------- resep

# Tiap halaman diberi cacat yang berbeda supaya kelas punya bahan
# membandingkan. Kolom terakhir adalah yang diuji di modul L4.
RESEP = {
    "SOP-01-Kepegawaian.pdf": [
        dict(cacat="bersih",   catatan="pembanding — pindaian yang baik"),
        dict(cacat="miring",   derajat=-1.8,
             catatan="tabel alur persetujuan cuti, halaman miring"),
        dict(cacat="pudar",    terang=1.28, kontras=0.55,
             catatan="tabel pengali upah lembur, fotokopi pudar"),
    ],
    "SOP-02-Pengadaan.pdf": [
        dict(cacat="miring",   derajat=1.1,
             catatan="tabel batas nilai kewenangan — inti kasus hibrida"),
        dict(cacat="lipatan",
             catatan="tabel sembilan tahapan pengadaan"),
    ],
    "SE-12-2026-Perjalanan-Dinas.pdf": [
        dict(cacat="tangan",
             baris=["Mohon ditindaklanjuti", "Divisi SDM", "3 Feb 2026"],
             catatan="disposisi tulis tangan — OCR tidak melihatnya"),
        dict(cacat="pudar",    terang=1.22, kontras=0.62,
             catatan="dua tabel tarif berdampingan, agak pudar"),
    ],
    "SOP-05-Keamanan-Informasi.pdf": [
        dict(cacat="bersih",   catatan="pembanding — dokumen berlaku"),
    ],
}


def olah(gbr: Image.Image, resep: dict) -> Image.Image:
    jenis = resep["cacat"]
    if jenis == "miring":
        gbr = miringkan(gbr, resep["derajat"])
    elif jenis == "pudar":
        gbr = kurangi_cahaya(gbr, resep["terang"], resep["kontras"])
        gbr = gbr.filter(ImageFilter.GaussianBlur(0.4))
    elif jenis == "lipatan":
        gbr = garis_lipatan(gbr)
        gbr = miringkan(gbr, 0.5)
    elif jenis == "tangan":
        gbr = tulisan_tangan(gbr, resep["baris"])

    # semua pindaian kena bintik; itu wajar
    return beri_bintik(gbr)


def cari(nama: str) -> Path | None:
    for p in ASAL.rglob(nama):
        return p
    return None


def main() -> None:
    TUJUAN.mkdir(exist_ok=True)
    ringkas = []

    for nama, resep_halaman in RESEP.items():
        sumber = cari(nama)
        if sumber is None:
            print(f"  ! {nama} tidak ditemukan, dilewati")
            continue

        asal = pymupdf.open(sumber)
        hasil = pymupdf.open()

        for no, resep in enumerate(resep_halaman):
            if no >= asal.page_count:
                break
            piksel = asal[no].get_pixmap(dpi=DPI_PINDAI)
            gbr = Image.frombytes("RGB", (piksel.width, piksel.height),
                                  piksel.samples)
            gbr = olah(gbr, resep)

            # JPEG mutu sedang — pemindai kantor memang begitu,
            # dan artefaknya ikut menyulitkan pembacaan
            penampung = io.BytesIO()
            gbr.save(penampung, "JPEG", quality=72)

            hal = hasil.new_page(width=asal[no].rect.width,
                                 height=asal[no].rect.height)
            hal.insert_image(hal.rect, stream=penampung.getvalue())

            ringkas.append((nama, no + 1, resep["cacat"], resep["catatan"]))

        keluar = TUJUAN / nama.replace(".pdf", "-PINDAI.pdf")
        hasil.save(keluar, deflate=True)
        hasil.close()
        asal.close()

        # bukti bahwa berkasnya benar-benar tanpa teks
        periksa = pymupdf.open(keluar)
        jumlah_teks = sum(len(h.get_text().strip()) for h in periksa)
        periksa.close()
        ukur = keluar.stat().st_size / 1024
        print(f"  {keluar.name:<44} {len(resep_halaman)} hal  "
              f"{ukur:6.0f} KB  teks: {jumlah_teks} karakter")

    print("\n  Peta cacat (untuk instruktur — jangan dibagikan ke peserta):")
    for nama, hal, cacat, catatan in ringkas:
        print(f"    {nama:<36} hal.{hal}  {cacat:<8} {catatan}")


if __name__ == "__main__":
    main()
