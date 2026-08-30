"""Pemeriksaan kesiapan lab.

Sebagian besar kegagalan lab bukan karena konsepnya sulit, melainkan karena
satu hal kecil di penyiapan: layanan belum hidup, model belum ditarik, paket
belum terpasang. Modul ini menemukan semuanya dalam beberapa detik, sebelum
peserta menghabiskan dua puluh menit menebak-nebak.

Aturan penting modul ini: JANGAN mengimpor langchain, chroma, atau apa pun
dari `ragcore` yang membutuhkannya di tingkat modul. Pemeriksaan ini harus
tetap berjalan justru di mesin yang paketnya belum lengkap. Yang boleh
diimpor hanya `config` dan `fingerprint`, yang keduanya murni pustaka bawaan.

Setiap fungsi periksa_* mengembalikan daftar langkah perbaikan, bukan
mencetak lalu menyimpannya di variabel global. Dengan begitu urutan dan
bentuk laporannya ditentukan di satu tempat: `jalankan()`.
"""
from __future__ import annotations

import importlib
import json
import sys
import urllib.request

from . import config, fingerprint

OK = "  [ OK ]"
FAILED = "  [GAGAL]"
NOTE = "  [catat]"

# modul yang diimpor -> nama paket yang dipasang lewat pip
REQUIRED_PACKAGE = {
    "langchain_core": "langchain",
    "langchain_text_splitters": "langchain-text-splitters",
    "langchain_community": "langchain-community",
    "langchain_chroma": "langchain-chroma",
    "langchain_ollama": "langchain-ollama",
    "pypdf": "pypdf",
    "rank_bm25": "rank_bm25",
}

OPTION_PACKAGE = {
    "sentence_transformers": "sentence-transformers  (untuk reranker, modul B4)",
    "streamlit": "streamlit             (untuk ui, modul A5)",
}

DOCUMENT_SUFFIX = (".pdf", ".md")
TEXT_THRESHOLD = 50
TIME_LIMIT = 6


def _exists(modul: str) -> bool:
    try:
        importlib.import_module(modul)
        return True
    except ImportError:
        return False


def check_package() -> list[str]:
    """Paket wajib harus ada; paket pilihan cukup dicatat bila belum ada."""
    print("\n1. Paket Python")
    issue: list[str] = []

    for modul, package in REQUIRED_PACKAGE.items():
        if _exists(modul):
            print(f"{OK} {package}")
        else:
            print(f"{FAILED} {package} belum terpasang")
            issue.append(f"pip install {package}")

    for modul, remark in OPTION_PACKAGE.items():
        if _exists(modul):
            print(f"{OK} {remark}")
        else:
            print(f"{NOTE} {remark} belum ada — opsional")
    return issue


def _available_models(dasar: str) -> set[str]:
    """Nama model di Ollama, lengkap dan tanpa tag (qwen3:8b dan qwen3)."""
    with urllib.request.urlopen(dasar + "/api/tags", timeout=TIME_LIMIT) as reply:
        data = json.loads(reply.read())
    name = {m["name"] for m in data.get("models", [])}
    return name | {n.split(":")[0] for n in name}


def check_ollama() -> list[str]:
    """Layanan hidup, dan kedua model yang dipakai lab sudah ditarik."""
    print("\n2. Layanan Ollama")
    if config.FAKE_MODE:
        print(f"{NOTE} MODE TIRUAN aktif — Ollama dilewati")
        return []

    issue: list[str] = []
    dasar = config.ollama_url()
    show = dasar.replace("http://", "")

    try:
        urllib.request.urlopen(dasar, timeout=4).read()
        print(f"{OK} layanan hidup di {show}")
    except Exception:
        # Apa pun sebabnya — koneksi ditolak, DNS, proxy — artinya sama saja
        # bagi peserta: layanannya belum siap dipakai.
        print(f"{FAILED} layanan tidak menjawab di {show}")
        return ["Jalankan Ollama (buka aplikasinya, atau: ollama serve)"]

    try:
        available = _available_models(dasar)
    except Exception as e:
        # Daftar model gagal dibaca bukan alasan menyatakan BELUM SIAP:
        # layanannya sudah terbukti hidup di pemeriksaan sebelumnya.
        print(f"{NOTE} tidak bisa membaca daftar model ({type(e).__name__})")
        return issue

    for name in (config.MODEL_CHAT, config.MODEL_EMBEDDING):
        if name in available or name.split(":")[0] in available:
            print(f"{OK} model {name}")
        else:
            print(f"{FAILED} model {name} belum ditarik")
            issue.append(f"ollama pull {name}")
    return issue


def _check_readability(file) -> list[str]:
    """Uji keterbacaan PDF — kebiasaan dari modul F4."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    issue: list[str] = []
    for p in file:
        if p.suffix.lower() != ".pdf":
            continue
        pembaca = PdfReader(str(p))
        content = sum(len((h.extract_text() or "").strip()) for h in pembaca.pages)
        if content < TEXT_THRESHOLD:
            print(f"{FAILED} {p.name} nyaris tanpa teks — kemungkinan hasil pindaian")
            issue.append(f"{p.name} perlu OCR atau diganti")
        else:
            print(f"{OK} {p.name} terbaca ({len(pembaca.pages)} hal, {content} karakter)")
    return issue


def check_document() -> list[str]:
    """Korpus ada, terbaca, dan set ujinya lengkap."""
    print("\n3. Dokumen dan set uji")
    if not config.DOCUMENT.exists():
        print(f"{FAILED} folder dokumen tidak ada: {config.DOCUMENT}")
        return ["Jalankan skrip dari dalam folder lab/src"]

    file = [
        p for p in config.DOCUMENT.rglob("*") if p.suffix.lower() in DOCUMENT_SUFFIX
    ]
    print(f"{OK} {len(file)} dokumen ditemukan")
    issue = _check_readability(file)

    # KORPUS PINDAIAN DIPERIKSA TERPISAH, dan itu bukan kelengkapan.
    #
    # Seluruh Hari 1 TX-AI12 bekerja pada scanned_documents/, bukan pada
    # documents/. Sebelumnya pemeriksa ini hanya menghitung korpus bersih, lalu
    # melaporkan "2 dokumen ditemukan" dan menyatakan lab SIAP - padahal empat
    # PDF pindaian yang menjadi inti kursus bisa saja tidak ada sama sekali.
    #
    # Singgahan .vlm.txt ikut dihitung karena tanpanya indexing akan
    # menjalankan ulang ekstraksi VLM: belasan menit per dokumen, tanpa
    # peringatan apa pun, dan peserta akan mengira programnya menggantung.
    if config.SCAN_DOCUMENT.exists():
        scan = sorted(config.SCAN_DOCUMENT.glob("*.pdf"))
        cache = list(config.SCAN_DOCUMENT.glob("*.vlm.txt"))
        if scan:
            print(f"{OK} {len(scan)} PDF pindaian, "
                  f"{len(cache)} sudah diekstrak")
            if len(cache) < len(scan):
                print(f"{NOTE} {len(scan) - len(cache)} belum "
                      "diekstrak — indexing akan lama (jalur VLM)")
        else:
            print(f"{FAILED} folder scanned_documents kosong")
            issue.append("python -m ragcore.commands.extract")
    else:
        print(f"{FAILED} folder scanned_documents tidak ada — "
              "seluruh Hari 1 tidak bisa dijalankan")
        issue.append("Periksa apakah folder lab lengkap")

    if config.TEST_SET.exists():
        total_count = len(json.loads(config.TEST_SET.read_text(encoding="utf-8")))
        print(f"{OK} testset.json berisi {total_count} kasus")
    else:
        print(f"{NOTE} testset.json belum ada — evaluasi di modul B6 tidak bisa jalan")
    return issue


def check_index() -> list[str]:
    """Indeks ada DAN dibangun dengan setelan yang sama seperti sekarang (F3)."""
    print("\n4. Indeks")
    if not (config.INDEX.exists() and config.CHUNKS_FILE.exists()):
        print(f"{NOTE} indeks belum ada. Jalankan:")
        print("         python -m ragcore.commands.index")
        return []

    matches, message = fingerprint.check()
    if matches:
        print(f"{OK} indeks sudah dibangun — siap dipakai menjawab")
        return []

    print(f"{FAILED} {message}")
    return ["python -m ragcore.commands.index --ulang"
            "  (indeks tidak cocok dengan config)"]


def run() -> int:
    """Jalankan seluruh pemeriksaan. Kembalikan 0 bila siap, 1 bila belum."""
    print("=" * 62)
    print("PEMERIKSAAN KESIAPAN LAB")
    print("=" * 62)
    print(f"  Python {sys.version.split()[0]}")

    from ragcore import config
    mode = "PRODUCTION — rahasia wajib dari environment" if config.IS_PRODUCTION \
        else "lab — kredensial demo diizinkan (host lokal saja)"
    print(f"  RAG_ENV: {config.RAG_ENV}  ({mode})")

    issue = check_package()
    try:
        issue += check_ollama() + check_document() + check_index()
    except ImportError:
        print("\n  (pemeriksaan lain dilewati karena ada paket yang belum terpasang)")

    print("\n" + "=" * 62)
    if issue:
        print("BELUM SIAP. Yang perlu dikerjakan:\n")
        # dict.fromkeys membuang duplikat tanpa mengubah urutan.
        for number, step in enumerate(dict.fromkeys(issue), start=1):
            print(f"  {number}. {step}")
        print("\nSetelah beres, jalankan lagi: python check.py")
        return 1

    print("SIAP. Langkah berikutnya:")
    # Perintah di sini HARUS bisa disalin-tempel apa adanya.
    # Sebelumnya tertulis "python index.py / answer.py / evaluate.py" -
    # nama berkas gaya TX-AI11 yang TIDAK ADA di lab ini. Pemeriksa
    # kesehatan yang menutup dengan perintah tidak berjalan merusak satu-
    # satunya hal yang ia janjikan: kepastian bahwa lab siap dipakai.
    print("  python -m ragcore.commands.index        bangun indeks")
    print("  python -m ragcore.commands.answer '...'    ajukan pertanyaan")
    print("  python -m ragcore.commands.evaluate         ukur retrieval")
    print("  python -m ragcore.commands.evaluate_hybrid ukur agent")
    return 0
