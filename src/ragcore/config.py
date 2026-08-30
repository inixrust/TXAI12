"""Fasad setelan — mengekspor ulang paket `settings` sebagai satu permukaan.

Setelan yang sesungguhnya kini dipecah menurut urusan di `ragcore/settings/`
(lihat docstring paket itu untuk peta dan alasannya). Modul ini menyatukannya
kembali agar antarmuka lama tetap utuh:

    from ragcore import config
    config.MODEL_CHAT, config.PG_URL, config.DPI_RENDER   # tetap bekerja

Kode BARU sebaiknya mengimpor modul yang spesifik, bukan lewat fasad ini:

    from ragcore.settings.security import IS_PRODUCTION
    from ragcore.settings.vision import DPI_RENDER

Dengan begitu ia hanya menarik urusan yang benar-benar dipakainya, dan tidak
ikut bergantung pada seluruh setelan aplikasi hanya untuk membaca satu nilai.

Modul ini tetap stdlib-only lewat rantai `settings` — `check.py` masih bisa
membacanya sebelum paket lain terpasang.
"""
from __future__ import annotations

# .env dibaca saat paket settings diimpor (di __init__-nya). Impor ini
# memicunya, jadi seluruh nilai di bawah sudah melihat variabel lingkungan
# yang benar.
from ragcore.settings._env import ROOT, flag, load_env
from ragcore.settings.database import (
    EMBEDDING_DIM,
    GUC_UNIT,
    PG_TABLE,
    PG_URL,
    PG_URL_APP,
    PG_URL_DIRECT,
    STORAGE,
)
from ragcore.settings.documents import (
    ACTIVE_STATUS,
    COVERAGE_THRESHOLD,
    MAX_UPLOAD_MB,
    MAX_UPLOAD_PAGES,
    NOT_FOUND,
    REVOKED_STATUS,
    REVOKED_TAGGER,
)
from ragcore.settings.mcp import (
    MCP_COMMAND,
    MCP_CONNECTION_NAME,
    ORACLE_CONNECTION,
    SQLCL_HOME,
)
from ragcore.settings.models import (
    DEFAULT_URL_OLLAMA,
    FAKE_MODE,
    MODEL_CHAT,
    MODEL_EMBEDDING,
    MODEL_RERANKER,
    NUM_CTX_CHAT,
    OLLAMA_URL,
    USE_RERANKER,
    ollama_url,
)
from ragcore.settings.observability import (
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    USE_TRACING,
)
from ragcore.settings.paths import (
    CACHE_SUFFIX,
    CHUNKS_FILE,
    COLLECTION_NAME,
    DOCUMENT,
    HYBRID_TEST_SET,
    INDEX,
    META,
    ORIGINAL_SOURCE,
    SCAN_DOCUMENT,
    TEST_SET,
)
from ragcore.settings.retrieval import (
    ARTICLED_KINDS,
    CHUNK_SIZE,
    N_CANDIDATES,
    N_FINAL,
    OVERLAP,
    PROSE_SEPARATOR,
    REGULATION_SEPARATOR,
    SELF_QUERY,
)
from ragcore.settings.security import (
    IS_PRODUCTION,
    RAG_ENV,
    ConfigError,
    app_credentials,
)
from ragcore.settings.session import (
    SESSION_COOKIE,
    SESSION_SECRET,
    SESSION_TTL,
)
from ragcore.settings.vision import (
    DPI_FALLBACK,
    DPI_RENDER,
    EMPTY_PAGE,
    EMPTY_PAGE_THRESHOLD,
    KEEP_ALIVE_VLM,
    MODEL_VISION,
    NUM_CTX_VLM,
    REASONING_VLM,
    UNREADABLE,
)

__all__ = [
    "ACTIVE_STATUS",
    "ARTICLED_KINDS",
    "CACHE_SUFFIX",
    "CHUNKS_FILE",
    "CHUNK_SIZE",
    "COLLECTION_NAME",
    "COVERAGE_THRESHOLD",
    "DEFAULT_URL_OLLAMA",
    "DOCUMENT",
    "DPI_FALLBACK",
    "DPI_RENDER",
    "EMBEDDING_DIM",
    "EMPTY_PAGE",
    "EMPTY_PAGE_THRESHOLD",
    "FAKE_MODE",
    "GUC_UNIT",
    "HYBRID_TEST_SET",
    "INDEX",
    "IS_PRODUCTION",
    "KEEP_ALIVE_VLM",
    "LANGFUSE_HOST",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "MAX_UPLOAD_MB",
    "MAX_UPLOAD_PAGES",
    "MCP_COMMAND",
    "MCP_CONNECTION_NAME",
    "META",
    "MODEL_CHAT",
    "MODEL_EMBEDDING",
    "MODEL_RERANKER",
    "MODEL_VISION",
    "NOT_FOUND",
    "NUM_CTX_CHAT",
    "NUM_CTX_VLM",
    "N_CANDIDATES",
    "N_FINAL",
    "OLLAMA_URL",
    "ORACLE_CONNECTION",
    "ORIGINAL_SOURCE",
    "OVERLAP",
    "PG_TABLE",
    "PG_URL",
    "PG_URL_APP",
    "PG_URL_DIRECT",
    "PROSE_SEPARATOR",
    "RAG_ENV",
    "REASONING_VLM",
    "REGULATION_SEPARATOR",
    "REVOKED_STATUS",
    "REVOKED_TAGGER",
    "ROOT",
    "SCAN_DOCUMENT",
    "SELF_QUERY",
    "SESSION_COOKIE",
    "SESSION_SECRET",
    "SESSION_TTL",
    "SQLCL_HOME",
    "STORAGE",
    "TEST_SET",
    "UNREADABLE",
    "USE_RERANKER",
    "USE_TRACING",
    "ConfigError",
    "app_credentials",
    "flag",
    "load_env",
    "ollama_url",
    "summarize",
]


def summarize() -> None:
    """Tampilkan setelan aktif. Berguna saat mendiagnosis masalah peserta."""
    print("  model chat      :", MODEL_CHAT,
          f"(num_ctx {NUM_CTX_CHAT})")
    print("  model embedding :", MODEL_EMBEDDING)
    print("  reranker        :", MODEL_RERANKER if USE_RERANKER else "dimatikan")
    print("  chunks        :", f"{CHUNK_SIZE} karakter, tumpang tindih {OVERLAP}")
    print("  kandidat -> akhir:", f"{N_CANDIDATES} -> {N_FINAL}")
    print("  storage     :", STORAGE
          + (f" ({PG_TABLE})" if STORAGE == "pgvector" else ""))
    print("  model vision    :", MODEL_VISION, f"@ {DPI_RENDER} dpi")
    print("  tracing Langfuse  :", LANGFUSE_HOST if USE_TRACING else "dimatikan")
    if FAKE_MODE:
        print("  MODE TIRUAN AKTIF — hasil tidak mencerminkan mutu sebenarnya")
