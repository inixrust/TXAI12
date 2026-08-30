"""Pembuat objek model, dengan jalur cadangan bila Ollama bermasalah.

Ketiga fungsi di sini di-cache: satu objek dipakai ulang selama proses hidup.
Tanpa itu, evaluasi yang memanggil pencarian puluhan kali akan membuat koneksi
baru setiap kali. `forget_model()` disediakan untuk pengujian.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .. import config
from .fake import FakeEmbedding, FakeLLM


def _ollama_args() -> dict[str, str]:
    """base_url hanya dikirim bila memang disetel — selebihnya biar bawaan."""
    return {"base_url": config.OLLAMA_URL} if config.OLLAMA_URL else {}


@lru_cache(maxsize=1)
def get_embedding() -> Any:
    """Model embedding. HARUS sama dengan yang dipakai membangun indeks (F3)."""
    if config.FAKE_MODE:
        return FakeEmbedding()

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=config.MODEL_EMBEDDING, **_ollama_args())


@lru_cache(maxsize=1)
def get_llm(num_ctx: int | None = None) -> Any:
    """Model chat. temperature=0 agar jawaban bisa diulang dan dibandingkan.

    `num_ctx` menimpa config.NUM_CTX_CHAT bila diisi. Dipakai perbandingan
    "konteks penuh" di L11, yang sengaja menyesuaikan jendela dengan seluruh
    korpus - satu-satunya pemanggil yang butuh nilai selain bawaan. Karena
    parameter ini ada, konstruksi ChatOllama tidak perlu bocor ke luar seam.

    Cache (maxsize=1) mengunci pada argumen: pemanggil bawaan berbagi satu
    objek, dan panggilan L11 dengan num_ctx berbeda menggusurnya sesaat -
    tidak masalah, karena L11 adalah perintah tersendiri, bukan jalur yang
    berselang-seling dengan pelayanan pertanyaan.
    """
    if config.FAKE_MODE:
        return FakeLLM()

    from langchain_ollama import ChatOllama

    # num_ctx eksplisit: lihat config.NUM_CTX_CHAT. Tanpa ini Ollama
    # memakai 4096 dan membuang prompt sistem diam-diam.
    return ChatOllama(model=config.MODEL_CHAT, temperature=0,
                      num_ctx=num_ctx or config.NUM_CTX_CHAT, **_ollama_args())


def get_vlm() -> Any:
    """Model vision untuk membaca halaman pindaian (L3).

    Dipisah dari get_llm() karena parameternya BUKAN sekadar model yang beda:
    keep_alive dan reasoning di sini soal KEBENARAN HASIL, bukan preferensi -
    lihat tabel pengukuran di config.KEEP_ALIVE_VLM dan config.REASONING_VLM.

    TIDAK di-cache. get_llm() aman dipakai ulang, tetapi VLM sengaja dilepas
    dari memori tiap halaman (keep_alive="0"); menyimpan objeknya di cache
    justru melawan tujuan itu.
    """
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=config.MODEL_VISION,
        temperature=0,
        num_ctx=config.NUM_CTX_VLM,
        # keep_alive="0" melepas model setiap selesai satu halaman. Lihat
        # config.KEEP_ALIVE_VLM: ini soal kebenaran hasil, bukan memori.
        keep_alive=config.KEEP_ALIVE_VLM,
        # reasoning=False WAJIB untuk model yang punya mode thinking.
        # Tanpa ini qwen3-vl:4b mengembalikan content KOSONG — lihat
        # tabel pengukuran di config.REASONING_VLM.
        reasoning=config.REASONING_VLM,
        **_ollama_args(),
    )


# Reranker sengaja dimuat MALAS (baru saat dipakai pertama kali).
# Kalau dimuat saat import, berkas modelnya sekitar 2 GB akan diunduh diam-diam
# dan peserta mengira programnya menggantung. Ini jebakan lab yang nyata.
@lru_cache(maxsize=1)
def get_reranker() -> Any | None:
    """Kembalikan objek reranker, atau None bila tidak tersedia.

    Sengaja tidak melempar errors: di laptop 8 GB reranker memang sebaiknya
    dimatikan, dan lab harus tetap jalan tanpanya. Hasil None ikut di-cache,
    sehingga percobaan pemuatan yang gagal tidak diulang di setiap pertanyaan.
    """
    if not config.USE_RERANKER or config.FAKE_MODE:
        return None

    try:
        from sentence_transformers import CrossEncoder

        print(f"  Memuat reranker {config.MODEL_RERANKER} ...")
        print("  (unduhan pertama sekitar 2 GB — biarkan sampai selesai)")
        return CrossEncoder(config.MODEL_RERANKER, max_length=512)
    except Exception as e:
        # Sengaja menangkap apa pun: paket belum ada, unduhan gagal, RAM habis.
        # Ketiganya berakhir sama — lab dilanjutkan tanpa penyusunan ulang.
        print(
            f"  Reranker tidak tersedia ({type(e).__name__}). "
            f"Lab dilanjutkan tanpa penyusunan ulang."
        )
        return None


def forget_model() -> None:
    """Buang objek model yang tersimpan — dipakai pengujian dan demo setelan."""
    get_embedding.cache_clear()
    get_llm.cache_clear()
    get_reranker.cache_clear()
