"""Empat pendekatan RAG tanpa embedding, dijalankan pada set uji yang sama (L11).

Dijalankan, bukan sekadar dijelaskan. Peserta menyusun tabel keputusannya
sendiri dari angka yang keluar di mesinnya sendiri - bukan dari tabel yang
sudah jadi di slide.

  1. konteks_penuh   - masukkan SELURUH korpus ke jendela konteks
  2. leksikal        - BM25 murni, tanpa sisi vektor sama sekali
  3. agentic         - model menelusuri korpus lewat tool, bertahap
  4. pageindex       - ringkasan berjenjang, model memilih cabang

Kesimpulan yang biasanya muncul - dan sebaiknya dibiarkan muncul sendiri:
jawabannya sering GABUNGAN. Korpus kecil dan pertanyaan lintas dokumen
cocok untuk konteks penuh; pencarian nomor dokumen dan istilah persis
justru lebih baik di leksikal daripada di vektor.
"""
from __future__ import annotations

import re
import time

from ragcore import config
from ragcore.agent.tools_hybrid import search_rules
from ragcore.evaluation.hybrid import TEST_SET
from ragcore.indexing.corpus import load_all
from ragcore.model import get_llm
from ragcore.retrieval.sources import source

APPROACH = ("konteks_penuh", "leksikal", "agentic", "pageindex")


def _corpus(include_scans: bool = True) -> list:
    """Korpus untuk perbandingan — TERMASUK hasil ekstraksi Hari 1.

    Tanpa halaman pindaian, korpusnya tinggal notulen dan satu SOP yang
    sudah dicabut: 8 chunks tanpa satu pun ketentuan yang berlaku.
    Perbandingan empat pendekatan di atas korpus semacam itu tidak
    mengukur apa pun.

    Ini jenis kesalahan yang mudah terjadi justru karena rapi: fungsi
    load_all() memang benar untuk TX-AI11, dan diam-diam menjadi salah
    di TX-AI12 ketika sebagian korpus pindah ke jalur ekstraksi.
    """

    chunks = list(load_all(quiet=True))
    # Ditunda: hasil VLM hanya dibaca bila diminta, dan modulnya menarik
    # rantai ekstraksi yang mahal untuk dimuat.
    if include_scans:
        from ragcore.indexing.corpus_scanned import load_scan

        chunks += load_scan(quiet=True)
    return chunks


# --------------------------------------------------------- 1. konteks penuh

# Ruang untuk pertanyaan, instruksi, dan jawaban - di luar korpus itu sendiri.
CADANGAN_TOKEN = 1200


def full_context(question: str, chunks: list | None = None,
                  quiet: bool = True) -> str:
    """Masukkan seluruh korpus ke prompt. Tidak ada retrieval sama sekali.

    Batasnya bukan kualitas melainkan ARITMETIKA: korpus lab muat dengan
    mudah, arsip 8.000 halaman tidak akan pernah muat. Dan biaya per
    pertanyaan naik sebanding besar korpus, bukan sebanding kesulitan
    pertanyaan - itu yang membuatnya mahal justru saat sering dipakai.

    num_ctx WAJIB DISETEL DI SINI, dan inilah jebakan yang paling merusak
    seluruh perbandingan L11:

    Bawaan Ollama adalah 4.096 token. Korpus lab ini ~4.984 token. Tanpa
    penyetelan, Ollama MEMOTONG prompt diam-diam - tidak ada errors, tidak
    ada peringatan - dan model menjawab "Informasi ini tidak ditemukan"
    untuk isi yang memang tidak pernah ia lihat.

    Terjadi sungguhan saat lab ini disusun: pertanyaan "berapa hari kerja
    hak cuti tahunan" dijawab tidak ditemukan, padahal jawabannya ada di
    karakter ke-10.014 dari 19.937 - tepat di paruh yang terbuang.

    Yang membuatnya berbahaya: kegagalan ini menyerupai KEBERHASILAN.
    Penolakan adalah perilaku yang benar bila informasinya memang tidak ada,
    jadi pendekatan "konteks penuh" akan terlihat sekadar berkinerja buruk -
    bukan terlihat rusak.
    """
    from ragcore.model import get_llm

    chunks = chunks if chunks is not None else _corpus()
    seluruhnya = "\n\n".join(d.page_content for d in chunks)

    commands = (
        f"Jawab HANYA dari dokumen berikut. Bila tidak ada, jawab persis: "
        f"{config.NOT_FOUND}\n\n{seluruhnya}\n\n"
        f"Pertanyaan: {question}"
    )

    perlu = len(commands) // 4 + CADANGAN_TOKEN
    if config.FAKE_MODE:
        return get_llm().invoke(commands).content.strip()

    if not quiet:
        print(f"    korpus perlu ~{perlu} token konteks")

    # Lewat seam model, dengan num_ctx disesuaikan korpus. Konstruksi
    # ChatOllama tetap di satu tempat (model/provider.py).
    return get_llm(num_ctx=perlu).invoke(commands).content.strip()


def corpus_size(chunks: list | None = None) -> dict:
    """Berapa besar korpusnya, dalam karakter dan perkiraan token."""
    chunks = chunks if chunks is not None else _corpus()
    seluruhnya = "\n\n".join(d.page_content for d in chunks)
    return {
        "potongan": len(chunks),
        "karakter": len(seluruhnya),
        "perkiraan_token": len(seluruhnya) // 4,
    }


# ------------------------------------------------------------- 2. leksikal

def lexical(question: str, k: int | None = None) -> list:
    """BM25 murni. Sisi vektor dimatikan sepenuhnya.

    Unggul persis di tempat embedding lemah: nomor dokumen ("SE-12/2026"),
    singkatan, nama orang, dan istilah yang harus cocok PERSIS. Embedding
    menganggap "SE-12" dan "SE-15" nyaris sama; BM25 tidak.
    """

    return source().bm25.invoke(question)[:(k or config.N_FINAL)]


# -------------------------------------------------------------- 3. agentic

def agentic(question: str, step_max: int = 4) -> str:
    """Model menelusuri korpus bertahap lewat tool, bukan sekali ambil.

    Lebih baik pada pertanyaan bertingkat yang jawabannya tersebar; jauh
    lebih mahal karena satu pertanyaan menjadi beberapa panggilan model.
    Bandingkan detiknya, bukan hanya ketepatannya.
    """
    from langchain.agents import create_agent


    agent = create_agent(
        model=get_llm(),
        tools=[search_rules],
        system_prompt=(
            f"Telusuri dokumen bertahap. Boleh mencari beberapa kali dengan "
            f"kata yang berbeda bila hasil pertama belum cukup. Maksimum "
            f"{step_max} pencarian. Bila tetap tidak ditemukan, jawab "
            f"persis: {config.NOT_FOUND}"),
    )
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content.strip()


# ------------------------------------------------------------ 4. pageindex

# Penanda bagian pada dokumen resmi Indonesia. Inilah batas makna yang
# ditulis penulisnya sendiri — jauh lebih berguna sebagai peta daripada
# baris pertama chunks.
SECTION_PATTERN = re.compile(
    r"^\s*((?:BAB|Pasal)\s+[IVXLC0-9]+[^\n]{0,70})", re.MULTILINE)


def build_map(chunks: list | None = None) -> dict[str, list[str]]:
    """Ringkasan berjenjang: dokumen -> daftar judul bagian.

    Peta dibangun SEKALI dan disimpan; yang dikirim ke model saat menjawab
    hanyalah petanya, bukan isinya. Itu yang membuatnya muat untuk korpus
    yang jauh lebih besar daripada konteks penuh.

    JANGAN memakai baris pertama chunks sebagai judul. Potongan di lab ini
    diawali jalur konteks yang disisipkan penanda.add_context() — dan jalur
    itu SAMA untuk seluruh chunks dalam satu dokumen. Hasilnya peta dengan
    satu judul per dokumen, yang membuat PageIndex merosot menjadi sekadar
    menebak nama berkas. Diuji: 6 dokumen, 1 judul masing-masing.
    """
    chunks = chunks if chunks is not None else _corpus()
    mapping: dict[str, list[str]] = {}

    for d in chunks:
        source = d.metadata.get("source", "?")
        mapping.setdefault(source, [])
        content = d.page_content or ""

        title = [j.strip() for j in SECTION_PATTERN.findall(content)]
        if not title:
            # Tidak ada penanda pasal — pakai baris isi pertama yang bukan
            # jalur konteks (jalur itu dikurung siku di baris paling atas).
            row = [b.strip() for b in content.splitlines() if b.strip()]
            title = [b[:80] for b in row if not b.startswith("[")][:1]

        for j in title:
            if j and j not in mapping[source]:
                mapping[source].append(j)
    return mapping


def pageindex(question: str, chunks: list | None = None) -> str:
    """Model memilih dokumen dari peta, baru isinya dibaca."""

    chunks = chunks if chunks is not None else _corpus()
    mapping = build_map(chunks)

    listing = "\n".join(
        f"- {source}\n" + "\n".join(f"    {j}" for j in title[:8])
        for source, title in mapping.items())

    option = get_llm().invoke(
        f"Peta dokumen yang tersedia:\n{listing}\n\n"
        f"Pertanyaan: {question}\n\n"
        f"Sebutkan HANYA nama berkas yang paling mungkin memuat jawabannya, "
        f"satu per baris, maksimum dua."
    ).content

    terpilih = [s for s in mapping if s and s in option]
    if not terpilih:
        terpilih = list(mapping)[:1]

    content = "\n\n".join(d.page_content for d in chunks
                      if d.metadata.get("source") in terpilih)
    return get_llm().invoke(
        f"Jawab HANYA dari dokumen berikut. Bila tidak ada, jawab persis: "
        f"{config.NOT_FOUND}\n\n{content}\n\nPertanyaan: {question}"
    ).content.strip()


# ------------------------------------------------------------ perbandingan

def compare_all(test_question: list[str] | None = None,
                     approach: tuple[str, ...] = APPROACH) -> dict:
    """Jalankan pendekatan terpilih pada pertanyaan yang sama, catat waktunya.

    Kembalikan {nama_pendekatan: {"detik": rata2, "jawaban": [...]}}.
    Peserta yang mengisi kolom ketepatannya sendiri - itu bagian latihannya.
    """

    if test_question is None:
        test_question = [k["tanya"] for k in TEST_SET
                          if k["jenis"] in ("dokumen_saja", "penolakan")]

    corpus = _corpus()
    measure = corpus_size(corpus)
    print(f"  Korpus: {measure['potongan']} potongan, {measure['karakter']} karakter, "
          f"~{measure['perkiraan_token']} token")
    if measure["perkiraan_token"] > 30000:
        print("  PERINGATAN: konteks penuh mungkin tidak muat di jendela model.")

    jalan = {
        "konteks_penuh": lambda t: full_context(t, corpus),
        "leksikal": lambda t: "\n".join(d.page_content[:200] for d in lexical(t)),
        "agentic": agentic,
        "pageindex": lambda t: pageindex(t, corpus),
    }

    result = {}
    for name in approach:
        print(f"\n  --- {name} ---")
        answer_text, failed, mulai = [], 0, time.perf_counter()
        for t in test_question:
            try:
                answer_text.append(jalan[name](t))
            except Exception as e:
                failed += 1
                answer_text.append(f"GAGAL: {type(e).__name__}: {e}")
                print(f"    GAGAL {type(e).__name__}: {e}")
            print(f"    {t[:60]}")
        seconds = (time.perf_counter() - mulai) / max(len(test_question), 1)
        result[name] = {"detik": round(seconds, 1), "gagal": failed,
                       "jawaban": answer_text}
        print(f"    rata-rata {seconds:.1f} detik per pertanyaan"
              + (f"  ({failed} GAGAL)" if failed else ""))

    # Kolom "gagal" WAJIB ditampilkan. Pendekatan yang melempar errors pada
    # setiap pertanyaan akan mencatat waktu 0,0 detik - dan tanpa kolom ini
    # angka itu terbaca sebagai "tercepat". Terjadi sungguhan saat lab ini
    # disusun: leksikal tampil 0,0 detik karena impornya salah, bukan karena
    # BM25 memang secepat itu.
    print(f"\n  {'pendekatan':<16}{'detik/tanya':>13}{'gagal':>8}")
    for name, a in result.items():
        marker = "  <- periksa" if a["gagal"] else ""
        print(f"  {name:<16}{a['detik']:>13.1f}{a['gagal']:>8}{marker}")
    print("\n  Kolom ketepatan diisi sendiri: baca jawabannya, bandingkan")
    print("  dengan acuan di testset_hybrid.json, lalu susun tabel keputusan.")
    return result
