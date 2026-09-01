"""Composition root — satu tempat yang merakit use-case dengan dependency NYATA.

Inilah bagian yang "tahu" implementasi konkret: retriever hybrid di atas
pgvector, dan model Ollama. Seluruh kode lain menerima service yang sudah
dirakit, jadi tidak ada modul use-case yang menyebut pgvector atau Ollama
secara langsung. Mengganti salah satunya cukup di sini.

Untuk tes, JANGAN memakai fungsi ini - rakit AnswerService sendiri dengan
retriever dan llm palsu. Justru itu gunanya dependency disuntik.
"""
from __future__ import annotations

from typing import Any

from ragcore.application.answer_service import AnswerService
from ragcore.domain import Document


class _HybridRetriever:
    """Adapter port Retriever ke pencari hybrid+rerank yang sesungguhnya.

    Membungkus retrieve_best() supaya AnswerService cukup tahu port-nya,
    bukan modul retrieval yang konkret.
    """

    def retrieve(self, question: str, *, k: int | None = None,
                 filters: Any = None, person: Any = None) -> list[Document]:
        from ragcore.retrieval.retriever import retrieve_best

        return retrieve_best(question, k=k, filters=filters, person=person)


def build_answer_service() -> AnswerService:
    """Rakit AnswerService dengan dependency produksi."""
    from ragcore.model import get_llm

    return AnswerService(retriever=_HybridRetriever(), llm=get_llm())


class _McpToolSource:
    """Adapter port ToolSource ke sesi MCP Oracle yang sesungguhnya.

    `operator=False` (bawaan produksi) memakai koneksi rag_baca hak-minimal
    yang tak dapat 'lihat semua'. Hanya jalur non-produksi (CLI operator) yang
    menyalakan operator=True. Lihat infra/oracle/04-operator-account.sql.
    """

    def __init__(self, quiet: bool = True, operator: bool = False):
        self._quiet = quiet
        self._operator = operator

    def session(self):
        from ragcore.agent.hybrid import database_session

        return database_session(quiet=self._quiet, operator=self._operator)


class _FilesystemBlobStore:
    """Adapter port BlobStore ke penyimpanan blob di filesystem."""

    def save(self, name: str, content: bytes):
        from ragcore.ingest import blob

        return blob.save(name, content)


class _PostgresTaskQueue:
    """Adapter port TaskQueue ke antrean tugas di Postgres."""

    def send(self, file_name: str, file_path: str, kind: str, *,
             unit, classification: str, pengunggah=None) -> int:
        from ragcore.ingest import queue

        return queue.send(file_name, file_path, kind,
                          unit=unit, classification=classification,
                          pengunggah=pengunggah)


def build_ingest_service():
    """Rakit IngestService dengan penyimpanan blob + antrean Postgres nyata."""
    from ragcore.application.ingest_service import IngestService

    return IngestService(blob_store=_FilesystemBlobStore(),
                        task_queue=_PostgresTaskQueue())


def build_agent_service(quiet: bool = True, operator: bool = False):
    """Rakit AgentService dengan dependency produksi: model Ollama, sesi MCP
    Oracle, dan create_agent langchain sebagai pabrik agent.

    `operator=False` (bawaan) = koneksi rag_baca hak-minimal untuk PRODUKSI
    (/agent/ask selalu ber-identitas, tak pernah butuh 'lihat semua').
    `operator=True` = koneksi rag_operator, hanya untuk CLI/pemeliharaan.
    """
    from langchain.agents import create_agent

    from ragcore.application.agent_service import AgentService
    from ragcore.model import get_llm

    return AgentService(
        llm=get_llm(),
        tool_source=_McpToolSource(quiet=quiet, operator=operator),
        agent_factory=create_agent,
    )
