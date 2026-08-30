"""Lapisan application: use-case sistem, terpisah dari cara ia dipanggil.

Setiap use-case menerima dependency BERAT-nya (retriever, model) lewat
konstruktor dan tidak melakukan I/O presentasi. Konstanta kebijakan tetap
dibaca langsung dari config - lihat "BATAS INJEKSI" di answer_service.py untuk
alasan batas itu dipilih. Composition root (`wiring`) merakit service dengan
implementasi nyata; adapter (CLI, Streamlit, API) memanggilnya.

Ini yang membuat diagram target di pertimbangan-arsitektur.md bisa berdiri:
`FastAPI -> ChatService -> domain`. ChatService = use-case di sini. Adapter API
memanggil service lalu MENYERIALISASI lewat AnswerOutcome.to_payload() - objek
hasil memuat tipe langchain yang tidak JSON-serializable, jadi boundary itu
yang memisahkan tipe internal dari kontrak transport.

Yang BELUM tercakup pola ini, dan jujur disebut: jalur agent (doc+DB, di
ragcore/agent) masih memakai identitas ContextVar global dan konstruksi
inline - ia belum diangkat ke lapisan ini.

    from ragcore.application import build_answer_service
    service = build_answer_service()
    hasil = service.ask("Berapa lama masa percobaan?", app_user=orang)
"""
from ragcore.application.agent_service import (
    AgentOutcome,
    AgentRunner,
    AgentService,
    ToolSource,
)
from ragcore.application.answer_service import (
    AnswerOutcome,
    AnswerService,
    Retriever,
)
from ragcore.application.ingest_service import (
    BlobStore,
    IngestReceipt,
    IngestService,
    TaskQueue,
)
from ragcore.application.wiring import (
    build_agent_service,
    build_answer_service,
    build_ingest_service,
)

__all__ = [
    "AgentOutcome",
    "AgentRunner",
    "AgentService",
    "AnswerOutcome",
    "AnswerService",
    "BlobStore",
    "IngestReceipt",
    "IngestService",
    "Retriever",
    "TaskQueue",
    "ToolSource",
    "build_agent_service",
    "build_answer_service",
    "build_ingest_service",
]
