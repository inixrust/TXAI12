"""Lapisan model: satu-satunya tempat yang tahu model itu datang dari mana.

Seluruh modul lain cukup memanggil `get_embedding()`, `get_llm()`, `get_vlm()`,
dan `get_reranker()` tanpa peduli apakah yang berjalan Ollama sungguhan atau
mode tiruan. Lapisan model yang terisolasi seperti ini bisa diganti tanpa
menyentuh logika RAG sama sekali - dan ia satu-satunya tempat yang membangun
objek ChatOllama/OllamaEmbeddings, jadi pindah pustaka model cukup di sini.
"""
from __future__ import annotations

from .provider import (
    forget_model,
    get_embedding,
    get_llm,
    get_reranker,
    get_vlm,
)

__all__ = [
    "annotations",
    "forget_model",
    "get_embedding",
    "get_llm",
    "get_reranker",
    "get_vlm",
]
