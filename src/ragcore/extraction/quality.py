"""Pemeriksaan mutu hasil ekstraksi VLM (L4).

Tidak ada satu pun fungsi di sini yang bisa memastikan teksnya BENAR.
Yang bisa dilakukan adalah menandai halaman yang PATUT DICURIGAI, supaya
waktu manusia terpakai pada halaman yang tepat.

Itu bukan kompromi, melainkan seluruh gagasannya. Memeriksa 8.000 halaman
secara manual mustahil; memeriksa 20 halaman yang sudah ditandai mesin
sangat mungkin.

Tiga lapis, dari yang paling murah:

  1. periksa_struktural  - bentuk teksnya, tanpa perlu tahu isi yang benar
  2. periksa_silang      - bandingkan ANGKA hasil VLM dengan hasil OCR
  3. sampel manusia      - di luar kode; quality_report() menyusun daftarnya
"""
from __future__ import annotations

import re

from ragcore import config

FAILED_TAGGER = (config.UNREADABLE, config.EMPTY_PAGE)

# Karakter yang wajar muncul di dokumen resmi berbahasa Indonesia. Dipakai
# untuk mendeteksi keluaran yang berubah menjadi simbol acak.
NORMAL_CHARS = ".,;:()[]%-/|–—"

# Tanda baca yang sah mengakhiri sebuah halaman. Batang tegak ikut karena
# halaman yang berakhir dengan baris tabel Markdown adalah hal biasa.
VALID_CLOSING = ".!?:)]|”"

# Penanda nomor halaman, di mana pun letaknya dalam baris.
PAGE_TAGGER = re.compile(
    r"(?:hal(?:aman)?|page|hlm)\.?\s*\d+", re.IGNORECASE)

# Panjang maksimum sebuah baris masih dianggap perabot, bukan isi.
# Kaki halaman dan kop pendek; kalimat SOP yang terpotong hampir selalu
# lebih panjang dari ini.
FURNITURE_ROW_LIMIT = 90


def _strip_furniture(text: str) -> str:
    """Buang kop/kaki halaman dari UJUNG teks, lalu kembalikan sisanya.

    Sebuah baris dianggap perabot bila pendek DAN tidak berakhir dengan
    tanda baca kalimat — atau memuat penanda nomor halaman.

    KENAPA PERLU, dan kenapa ini bukan sekadar kerapian: model yang berbeda
    memperlakukan kaki halaman berbeda pula. qwen2.5vl:3b mengabaikannya;
    qwen3-vl:4b menyalinnya. Halaman yang berakhir

        "Dokumen internal - dilarang diperbanyak tanpa izin  Hal. 3"

    tidak berakhir dengan tanda baca, dan pemeriksaan penutup menganggapnya
    terpotong. Akibatnya terukur: SELURUH 8 halaman uji ditandai perlu
    ditinjau — sama saja dengan tidak menyaring apa pun. Daftar tinjau yang
    selalu penuh akan berhenti dibaca, dan lapis 1 kehilangan seluruh gunanya.

    Paling banyak tiga baris dibuang. Lebih dari itu bukan lagi perabot,
    melainkan keluaran yang memang bermasalah.
    """
    row = text.rstrip().splitlines()
    for _ in range(3):
        while row and not row[-1].strip():
            row.pop()
        if not row:
            break
        akhir = row[-1].strip()
        pendek = len(akhir) <= FURNITURE_ROW_LIMIT
        bertanda_halaman = bool(PAGE_TAGGER.search(akhir))
        berakhir_kalimat = akhir.endswith((".", "!", "?", ":", ")", "]", "|"))
        if bertanda_halaman or (pendek and not berakhir_kalimat):
            row.pop()
            continue
        break
    return "\n".join(row).rstrip()


# --------------------------------------------------- lapis 1: struktural

def check_structural(text: str, panjang_min: int = 200) -> dict:
    """Kembalikan daftar kecurigaan pada satu halaman hasil ekstraksi.

    Seluruhnya otomatis dan nyaris tanpa biaya - jalankan ke semua halaman.
    """
    curiga: list[str] = []
    bersih = (text or "").strip()

    if len(bersih) < panjang_min:
        curiga.append(f"terlalu pendek ({len(bersih)} karakter)")

    for tagger in FAILED_TAGGER:
        n = bersih.count(tagger)
        if n:
            curiga.append(f"{n}x {tagger}")

    # Model kadang berhenti di tengah kalimat saat kehabisan anggaran keluaran.
    # Perabot halaman dibuang dulu — halaman yang berakhir "Hal. 3" itu utuh,
    # bukan terpotong. Lihat _strip_furniture().
    furniture_without = _strip_furniture(bersih)
    if (furniture_without
            and furniture_without[-1] not in VALID_CLOSING
            and furniture_without[-1] not in "\"'"):
        curiga.append("berakhir tanpa tanda baca - kemungkinan terpotong")

    # Pengulangan berturut-turut menandakan model tersangkut pada satu baris.
    row = [b.strip() for b in bersih.split("\n") if b.strip()]
    for i in range(len(row) - 2):
        if row[i] == row[i + 1] == row[i + 2]:
            curiga.append("baris berulang tiga kali - model tersangkut")
            break

    # Proporsi karakter yang wajar. Ekstraksi yang gagal menghasilkan simbol
    # acak dalam jumlah tak lazim.
    if bersih:
        normal = sum(c.isalnum() or c.isspace() or c in NORMAL_CHARS
                    for c in bersih)
        rasio = normal / len(bersih)
        if rasio < 0.85:
            curiga.append(f"banyak karakter tak lazim (rasio wajar {rasio:.2f})")

    return {"panjang": len(bersih), "curiga": curiga, "lolos": not curiga}


# ------------------------------------------------------- lapis 2: silang

def numbers_in(text: str) -> set[str]:
    """Ambil semua angka, dinormalkan agar bisa dibandingkan antar-jalur.

    Format Indonesia memakai titik sebagai pemisah ribuan:
        'Rp 15.000.000'  ->  '15000000'

    Angka satu digit dibuang: nomor ayat dan penomoran daftar menghasilkan
    terlalu banyak kecocokan palsu untuk bisa berguna.
    """
    result = set()
    for m in re.findall(r"\d[\d.,]*\d|\d", text or ""):
        bersih = m.replace(".", "").replace(",", "")
        if bersih.isdigit() and len(bersih) >= 2:
            result.add(bersih.lstrip("0") or "0")
    return result


# Angka sebesar ini ke atas dianggap BERKONSEKUENSI: nominal rupiah, batas
# nilai kewenangan, tarif. Di bawahnya adalah nomor pasal, nomor halaman,
# jumlah hari, dan tahun - yang lazim muncul di kop dan kaki halaman.
CONSEQUENTIAL_DIGITS = 5


def cross_check(vlm_text: str, ocr_text: str) -> dict:
    """Bandingkan himpunan angka dari dua jalur ekstraksi.

    Kenapa HANYA angka? Karena VLM merapikan tata letak sedangkan OCR
    mengikuti urutan piksel - susunan katanya pasti berbeda. Membandingkan
    seluruh teks menghasilkan ketidaksepakatan palsu di mana-mana, dan
    sinyal yang sesungguhnya tenggelam di dalamnya.

    Angka tidak begitu. Dan di dokumen SOP, tarif, serta kontrak, justru
    angka yang paling berkonsekuensi bila salah dibaca.

    KEDUA ARAH TIDAK SAMA BAHAYANYA - dan ini pelajarannya sendiri:

      dikarang (ada di VLM, tidak di OCR)
          Selalu ditandai. Inilah kegagalan yang berbahaya: VLM membaca
          "Rp 15.000.000" menjadi "Rp 150.000.000", dan hasilnya terlihat
          serapi teks yang benar.

      terlewat (ada di OCR, tidak di VLM)
          Hanya ditandai bila angkanya BERKONSEKUENSI. Nomor dokumen dan
          nomor halaman di kop selalu terbaca OCR dan hampir selalu
          diabaikan VLM - itu perilaku yang BENAR, bukan cacat. Menandainya
          membuat setiap halaman berkop tampak mencurigakan, dan daftar
          tinjau yang penuh alarm palsu akan berhenti dibaca.
    """
    a, b = numbers_in(vlm_text), numbers_in(ocr_text)
    combined = a | b
    match = len(a & b) / len(combined) if combined else 1.0

    dikarang = a - b
    missed = b - a
    missed_important = {n for n in missed if len(n) >= CONSEQUENTIAL_DIGITS}

    # Kecocokan yang hanya menghitung angka berkonsekuensi - ini yang layak
    # dipakai menilai, sedangkan kecocokan_angka di atas untuk ditampilkan.
    besar_a = {n for n in a if len(n) >= CONSEQUENTIAL_DIGITS}
    besar_b = {n for n in b if len(n) >= CONSEQUENTIAL_DIGITS}
    combined_large = besar_a | besar_b
    important_match = (
        len(besar_a & besar_b) / len(combined_large) if combined_large else 1.0)

    return {
        "kecocokan_angka": round(match, 2),
        "kecocokan_berkonsekuensi": round(important_match, 2),
        "hanya_di_vlm": sorted(dikarang)[:10],
        "hanya_di_ocr": sorted(missed)[:10],
        "terlewat_penting": sorted(missed_important)[:10],
        "perlu_diperiksa": bool(dikarang) or bool(missed_important),
    }


def extract_with_ocr(path_pdf, number: int) -> str:
    """Jalur pembanding untuk lapis 2. Kembalikan '' bila OCR tak tersedia.

    Sengaja tidak menjadikan pytesseract dependensi wajib: lapis 1 dan 3
    tetap berguna tanpa OCR, dan memaksa seluruh kelas memasang Tesseract
    beserta paket bahasa Indonesianya hanya untuk satu lapis pemeriksaan
    bukan tukar-tambah yang sepadan.
    """
    try:
        import io

        import pymupdf
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        dok = pymupdf.open(str(path_pdf))
    except Exception:
        return ""

    try:
        # OCR justru butuh DPI tinggi - ia bekerja pada bentuk huruf,
        # bukan pada pemahaman gambar seperti VLM.
        piksel = dok[number].get_pixmap(dpi=300)
        image = Image.open(io.BytesIO(piksel.tobytes("png")))
        return pytesseract.image_to_string(image, lang="ind")
    except Exception:
        return ""
    finally:
        dok.close()


# ---------------------------------------------------------------- laporan

def quality_report(vlm_page: dict[int, str],
                 ocr_page: dict[int, str] | None = None) -> list[int]:
    """Cetak ringkasan mutu, kembalikan daftar halaman yang perlu ditinjau.

    halaman_vlm / halaman_ocr: {nomor_halaman: teks}
    """
    review_pages: list[int] = []

    for no, text in sorted(vlm_page.items()):
        lapor = check_structural(text)
        row = f"  hal.{no:>3}  {lapor['panjang']:>5} karakter"

        if ocr_page and ocr_page.get(no, "").strip():
            cross = cross_check(text, ocr_page[no])
            row += f"  angka cocok {cross['kecocokan_berkonsekuensi']:>4.0%}"
            if cross["hanya_di_vlm"]:
                lapor["curiga"].append(
                    f"angka hanya muncul di VLM, kemungkinan salah baca: "
                    f"{cross['hanya_di_vlm'][:3]}")
            if cross["terlewat_penting"]:
                lapor["curiga"].append(
                    f"angka berkonsekuensi terlewat VLM: "
                    f"{cross['terlewat_penting'][:3]}")
        else:
            row += "  angka cocok    -"

        if lapor["curiga"]:
            review_pages.append(no)
            print(row + "   PERLU TINJAU")
            for c in lapor["curiga"]:
                print(f"              - {c}")
        else:
            print(row + "   lolos")

    print(f"\n  {len(review_pages)} dari {len(vlm_page)} halaman perlu "
          f"dibaca manusia: {review_pages or '-'}")
    print("  Dua lapis pertama TIDAK memutuskan benar atau salah. Keduanya")
    print("  hanya menyaring mana yang layak memakai waktu manusia.")
    return review_pages


def tag_chunks(chunks, review_pages: set[int],
                    match: dict[int, float] | None = None) -> None:
    """Pasang penanda mutu ke metadata, untuk dipakai menyaring di Hari 2.

    Nilainya: "lolos" | "perlu_tinjau" | "terverifikasi" (dipasang manusia
    setelah lapis 3). Penyaring di L6 memakai penanda ini untuk menahan
    chunks yang angkanya belum bisa dipercaya.
    """
    for p in chunks:
        if p.metadata.get("ekstraksi") != "vlm":
            continue
        page_no = p.metadata.get("page")
        p.metadata["mutu_ekstraksi"] = (
            "perlu_tinjau" if page_no in review_pages else "lolos")
        if match and page_no in match:
            p.metadata["kecocokan_angka"] = match[page_no]
