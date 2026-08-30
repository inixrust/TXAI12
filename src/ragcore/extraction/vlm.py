"""Ekstraksi halaman yang tidak punya lapisan teks, memakai model vision.

Modul F4 di TX-AI11 berhenti pada diagnosis: PDF hasil pindaian menghasilkan
indeks kosong TANPA satu pun galat. Di sini diagnosis itu ditindaklanjuti.

Rancangan yang perlu diperhatikan: hasil VLM disinggahkan ke berkas .vlm.txt
di sebelah PDF-nya. Ekstraksi satu arsip sungguhan bisa memakan berjam-jam,
dan indexing ulang adalah hal yang akan dilakukan berkali-kali selama
kelas. Tanpa singgahan, setiap percobaan ulang berarti menunggu dari nol.
"""
from __future__ import annotations

import base64
from pathlib import Path

from ragcore import config

# Prompt ekstraksi. Butir 4 dan 5 adalah yang terpenting: keduanya memberi
# model jalan keluar yang jujur. Tanpa itu, model yang tidak bisa membaca
# sesuatu akan MENGARANG — dan karangannya terlihat serapi teks yang benar.
EXTRACTION_PROMPT = f"""Salin SELURUH teks yang terlihat pada gambar halaman dokumen ini.

Aturan:
1. Salin apa adanya. JANGAN meringkas, menafsirkan, atau memperbaiki.
2. Pertahankan struktur: judul, nomor pasal, penomoran ayat, dan daftar.
3. Tabel ditulis ulang sebagai tabel Markdown, dengan judul kolom yang benar.
4. Bila ada bagian yang tidak terbaca jelas, tulis {config.UNREADABLE} di
   posisinya. JANGAN menebak isinya.
5. Bila halaman kosong atau hanya berisi gambar tanpa teks, tulis
   {config.EMPTY_PAGE}.
6. Jangan menambahkan komentar, penjelasan, atau kalimat pembuka apa pun.
   Keluarkan hanya isi halamannya."""


def blank_pages(page: list, threshold: int | None = None) -> list[int]:
    """Kembalikan indeks halaman yang nyaris tanpa lapisan teks."""
    threshold = config.EMPTY_PAGE_THRESHOLD if threshold is None else threshold
    return [i for i, h in enumerate(page)
            if len((h.page_content or "").strip()) < threshold]


def page_to_image(path_pdf: str | Path, number: int,
                        dpi: int | None = None) -> str:
    """Render satu halaman PDF menjadi PNG, kembalikan sebagai base64.

    DPI menentukan berapa banyak token visual yang dihasilkan, dan token
    visual itulah yang memakan VRAM. Lihat konfig.DPI_RENDER — jangan
    menaikkannya di sini, naikkan di satu tempat itu.
    """
    import pymupdf

    dok = pymupdf.open(str(path_pdf))
    try:
        image = dok[number].get_pixmap(dpi=dpi or config.DPI_RENDER)
        return base64.b64encode(image.tobytes("png")).decode()
    finally:
        dok.close()


def degenerate_output(text: str) -> bool:
    """Apakah keluaran model rusak berupa satu karakter yang berulang?

    Ini kegagalan yang paling perlu ditangkap otomatis, karena ia TIDAK
    memunculkan galat. Model yang kehabisan ruang untuk token visual akan
    mengeluarkan sesuatu seperti '@@@@@@@@@@@@@@@' dan mengembalikannya
    dengan status sukses. Tanpa pemeriksaan ini, halaman semacam itu masuk
    indeks sebagai potongan yang sah.
    """
    bersih = (text or "").strip()
    if not bersih:
        return True
    # Sedikit sekali karakter unik pada keluaran yang panjangnya tidak sepele.
    return len(set(bersih)) < 5 and len(bersih) > 8


def _call_vlm(path_pdf: str | Path, number: int, dpi: int,
              trace_meta: dict | None = None) -> str:
    from ragcore.domain import HumanMessage
    from ragcore.model import get_vlm

    # Konstruksi objek model ada di model/provider.py, bukan di sini: itu
    # satu-satunya tempat yang membangun ChatOllama, jadi pindah pustaka model
    # tidak menyentuh jalur ekstraksi. Parameter vision (keep_alive, reasoning)
    # yang menentukan kebenaran hasil juga tinggal di sana, terdokumentasi.
    vlm = get_vlm()
    image = page_to_image(path_pdf, number, dpi=dpi)

    message = HumanMessage(content=[
        {"type": "text", "text": EXTRACTION_PROMPT},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{image}"}},
    ])

    # Jejak Langfuse untuk ekstraksi - inilah yang dulu HILANG: pemanggilan
    # model vision tidak pernah membawa callback, jadi dokumen yang diunggah
    # diproses tanpa satu pun jejak. Sekarang tiap halaman menjadi satu jejak,
    # dikelompokkan per dokumen lewat session, dan teratribusi ke pengunggah.
    # invoke_config aman saat tracing mati (mengembalikan {}).
    config_jejak = {}
    if trace_meta is not None:
        from ..tracing import invoke_config
        config_jejak = invoke_config(
            "ekstraksi-vlm", session=trace_meta.get("session"),
            tag=["ingest", "vlm"], berkas=trace_meta.get("berkas"),
            halaman=number, dpi=dpi,
            langfuse_user_id=trace_meta.get("nip"))
    return vlm.invoke([message], config=config_jejak).content.strip()


def unload_model() -> None:
    """Paksa Ollama melepas model vision dari memori.

    keep_alive="0" seharusnya sudah melakukannya, tetapi pelepasan itu
    berjalan asinkron dan tidak selalu selesai sebelum permintaan berikutnya
    datang. Saat sebuah halaman terbukti rusak, kita perlu kepastian — bukan
    harapan — bahwa percobaan berikutnya memakai model yang segar.
    """
    import subprocess

    try:
        subprocess.run(["ollama", "stop", config.MODEL_VISION],
                       capture_output=True, timeout=30)
    except Exception:
        pass    # Bukan alasan menghentikan ekstraksi; percobaan ulang tetap jalan.


def extract_with_vlm(path_pdf: str | Path, number: int,
                       quiet: bool = True, trace_meta: dict | None = None) -> str:
    """Kembalikan teks satu halaman hasil pembacaan model vision.

    Dua percobaan ulang, dan URUTANNYA penting karena ada DUA kegagalan
    berbeda yang gejalanya persis sama:

      1. Model tersangkut. Kerusakannya MENULAR ke halaman berikutnya selama
         model masih termuat. Obatnya melepas model, lalu ulangi pada DPI
         yang sama - dan halaman yang tadi menghasilkan 31 karakter langsung
         terbaca utuh.

      2. Resolusi terlalu tinggi untuk model ini. Melepas model tidak
         menolong; yang menolong adalah MENURUNKAN DPI. Turun, bukan naik -
         kebalikan dari naluri yang wajar saat hasilnya buruk.

    Karena gejalanya sama, keduanya tidak bisa dibedakan tanpa mencoba.
    Jadi dicoba berurutan, dari yang paling murah.
    """
    result = _call_vlm(path_pdf, number, config.DPI_RENDER, trace_meta)
    if not degenerate_output(result):
        return result

    # Percobaan 1: anggap modelnya yang tersangkut.
    if not quiet:
        print("[rusak, lepas model & ulangi]", end=" ", flush=True)
    unload_model()
    result = _call_vlm(path_pdf, number, config.DPI_RENDER, trace_meta)
    if not degenerate_output(result):
        return result

    # Percobaan 2: anggap resolusinya yang kelewat tinggi.
    if not quiet:
        print(f"[masih rusak, turun ke {config.DPI_FALLBACK} dpi]",
              end=" ", flush=True)
    unload_model()
    result = _call_vlm(path_pdf, number, config.DPI_FALLBACK, trace_meta)
    if not degenerate_output(result):
        return result

    # Menyerah dengan JUJUR. Menyimpan '@@@@@@@' ke singgahan jauh lebih
    # buruk daripada menandainya tidak terbaca: yang pertama masuk indeks
    # sebagai chunks yang sah, yang kedua tertangkap lapis 1.
    if not quiet:
        print("[gagal, ditandai tidak terbaca]", end=" ", flush=True)
    return config.UNREADABLE


# ------------------------------------------------------------- singgahan

def _cache_path(path_pdf: Path) -> Path:
    return path_pdf.with_suffix(config.CACHE_SUFFIX)


ORIGIN_TAGGER = "===DIBACA-OLEH "


def read_cache(path_pdf: str | Path) -> dict[int, str]:
    """Kembalikan {nomor_halaman: teks} dari berkas singgahan, bila ada."""
    file = _cache_path(Path(path_pdf))
    if not file.exists():
        return {}

    stored: dict[int, str] = {}
    for blok in file.read_text(encoding="utf-8").split("===HALAMAN "):
        number, separator, content = blok.partition(":\n")
        if separator and number.strip().isdigit():
            stored[int(number)] = content.rstrip("\n")
    return stored


def cache_origin(path_pdf: str | Path) -> dict[str, str]:
    """Model dan DPI yang BENAR-BENAR menghasilkan singgahan ini.

    KENAPA INI PERLU DICATAT. Tanpa ini, penanda asal di metadata diisi dari
    konfigurasi yang sedang berlaku SAAT PENGINDEKSAN - bukan saat ekstraksi.
    Akibatnya sitasi bisa menyebut model yang tidak pernah membaca halaman itu.

    Terbukti di lab: ekstraksi dijalankan dengan qwen2.5vl:3b, indexing
    dijalankan tanpa menyetel MODEL_VISION, dan antarmuka menampilkan
    "dibaca qwen3-vl:4b" pada teks yang sama sekali bukan hasil model itu.

    Ini bukan cacat kosmetik. Seluruh Hari 1 mengajarkan bahwa mutu ekstraksi
    harus bisa ditelusuri; penanda asal yang salah menghapus kemampuan itu
    justru pada saat ia paling dibutuhkan - ketika sebuah angka diragukan
    dan orang bertanya "ini dibaca pakai apa?".
    """
    file = _cache_path(Path(path_pdf))
    if not file.exists():
        return {}
    start_row = file.read_text(encoding="utf-8").split("\n", 1)[0]
    if not start_row.startswith(ORIGIN_TAGGER):
        return {}       # singgahan versi lama, tanpa catatan asal
    section = start_row[len(ORIGIN_TAGGER):].strip().split(" @ ")
    origin = {"model_ekstraksi": section[0]}
    if len(section) > 1 and section[1].rstrip(" dpi").isdigit():
        origin["dpi_ekstraksi"] = section[1].rstrip(" dpi")
    return origin


def write_cache(path_pdf: str | Path, page: dict[int, str]) -> Path:
    """Simpan hasil ekstraksi agar tidak perlu menjalankan VLM lagi.

    Baris pertama mencatat SIAPA yang membacanya. Lihat cache_origin().
    """
    file = _cache_path(Path(path_pdf))
    header = f"{ORIGIN_TAGGER}{config.MODEL_VISION} @ {config.DPI_RENDER} dpi\n"
    file.write_text(
        header + "".join(f"===HALAMAN {no}:\n{content}\n"
                         for no, content in sorted(page.items())),
        encoding="utf-8")
    return file


# ------------------------------------------------------------- pemuatan

def load_pdf_smart(path_pdf: str | Path, use_cache: bool = True,
                    quiet: bool = False, trace_meta: dict | None = None) -> list:
    """Muat PDF; halaman tanpa lapisan teks dialihkan ke VLM.

    Dokumen biasa melewati jalur yang persis sama dengan TX-AI11 — tidak ada
    biaya tambahan bagi PDF yang memang punya lapisan teks.
    """
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from langchain_community.document_loaders import PyPDFLoader

    path_pdf = Path(path_pdf)
    page = PyPDFLoader(str(path_pdf)).load()
    empty = blank_pages(page)

    # Penanda asal dipasang untuk SEMUA halaman, termasuk yang tidak dipindai.
    # Kalau hanya halaman VLM yang ditandai, filters "bukan hasil VLM" harus
    # menangani nilai yang hilang — dan itu selalu terlupakan di satu tempat.
    for h in page:
        h.metadata["ekstraksi"] = "teks"

    if not empty:
        return page

    if not quiet:
        print(f"  {path_pdf.name}: {len(empty)} dari {len(page)} halaman "
              f"tanpa lapisan teks -> jalur VLM")

    stored = read_cache(path_pdf) if use_cache else {}
    # Asal yang TERCATAT di singgahan menang atas konfigurasi yang sedang
    # berlaku. Halaman yang dibaca ulang di bawah memakai konfigurasi
    # sekarang, jadi asalnya ditimpa per halaman.
    old_origin = cache_origin(path_pdf) if use_cache else {}
    new = False

    for i in empty:
        dari_singgahan = i in stored
        if dari_singgahan:
            text = stored[i]
            if not quiet:
                print(f"    hal.{i}: dari singgahan ({len(text)} karakter)")
        else:
            if not quiet:
                print(f"    hal.{i}: memanggil VLM...", end=" ", flush=True)
            text = extract_with_vlm(path_pdf, i, quiet=quiet,
                                    trace_meta=trace_meta)
            stored[i] = text
            new = True
            if not quiet:
                print(f"{len(text)} karakter")

        # Halaman dari singgahan memakai asal yang TERCATAT di singgahan itu;
        # halaman yang baru saja dibaca memakai konfigurasi sekarang.
        origin = old_origin if dari_singgahan else {}

        page[i].page_content = text
        page[i].metadata["ekstraksi"] = "vlm"
        page[i].metadata["model_ekstraksi"] = origin.get(
            "model_ekstraksi", config.MODEL_VISION)
        page[i].metadata["dpi_ekstraksi"] = int(origin.get(
            "dpi_ekstraksi", config.DPI_RENDER))

    if use_cache and new:
        write_cache(path_pdf, stored)

    return page
