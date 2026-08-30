"""Adapter HTTP: memanggil use-case, mengirim to_payload() sebagai JSON.

Seluruh berkas ini menguji API TANPA Ollama, Postgres, maupun MCP - service
palsu DISUNTIK lewat create_api(). Ini pembuktian akhir arsitektur: lapisan
HTTP hanya adapter tipis di atas application, dan bisa diuji utuh tanpa satu
pun layanan berat. Kalau suatu saat handler mulai memanggil get_llm() atau
open_store() langsung, tes ini gagal karena butuh layanan yang tidak ada.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from ragcore.api import create_api


class FakeAnswerService:
    """Meniru AnswerService.ask -> objek dengan to_payload()."""

    def __init__(self, payload):
        self._payload = payload
        self.seen = None

    def ask(self, question, *, app_user=None, person=None, k=None, session=None):
        self.seen = {"question": question, "k": k,
                     "app_user": app_user, "person": person}
        return _Outcome(self._payload)


class FakeAgentService:
    def __init__(self, payload):
        self._payload = payload
        self.seen = None

    async def ask_once(self, question, *, identity=None, tool_all=False):
        self.seen = {"question": question, "identity": identity}
        return _Outcome(self._payload)


class _Outcome:
    def __init__(self, payload):
        self._payload = payload

    def to_payload(self):
        return self._payload


class FakeIngestService:
    def __init__(self):
        self.seen = None

    def submit(self, filename, content, *, uploader, kind="sop",
               classification="terbatas"):
        self.seen = {"filename": filename, "uploader": uploader,
                     "kind": kind, "classification": classification}
        unit = getattr(uploader, "unit", None)
        return _Outcome({"task_id": 7, "name": filename, "unit": unit,
                         "classification": classification})


def _client(answer_payload=None, agent_payload=None):
    ans = FakeAnswerService(answer_payload or {"content": "3 bulan", "sources": []})
    agt = FakeAgentService(agent_payload or {"answer": "3 bulan", "tools_called": []})
    ing = FakeIngestService()
    app = create_api(ans, agt, ing)
    return TestClient(app), ans, agt, ing


def test_health():
    client, _, _, _ing = _client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ask_memanggil_answer_service_dan_kirim_payload():
    client, ans, _, _ing = _client(answer_payload={"content": "Masa percobaan 3 bulan.",
                                             "coverage": 1.0, "sources": [],
                                             "warnings": []})
    r = client.post("/ask", json={"question": "Berapa lama masa percobaan?", "k": 4},
                    headers=_valid_auth())

    assert r.status_code == 200
    assert r.json()["content"] == "Masa percobaan 3 bulan."
    # pertanyaan + k benar-benar diteruskan ke service
    assert ans.seen["question"] == "Berapa lama masa percobaan?"
    assert ans.seen["k"] == 4


def test_agent_ask_memanggil_agent_service():
    client, _, agt, _ing = _client(agent_payload={"answer": "Sudah sesuai.",
                                            "tools_called": ["search_rules", "sql_run"]})
    r = client.post("/agent/ask", json={"question": "Apakah cuti Budi sesuai SOP?"},
                    headers=_valid_auth())

    assert r.status_code == 200
    assert "search_rules" in r.json()["tools_called"]
    assert agt.seen["question"] == "Apakah cuti Budi sesuai SOP?"


def test_question_wajib():
    client, _, _, _ing = _client()
    r = client.post("/ask", json={}, headers=_valid_auth())
    assert r.status_code == 400
    assert "question" in r.json()["error"]


def test_body_bukan_json_ditolak_rapi():
    client, _, _, _ing = _client()
    r = client.post("/ask", content=b"bukan json", headers=_valid_auth())
    assert r.status_code == 400


# --- autentikasi: identitas dari Basic auth diteruskan ke service ---------

def _valid_auth() -> dict:
    from ragcore.domain.users import REGISTRY
    return _basic(next(iter(REGISTRY)), "lab2026")


def _basic(nip: str, password: str) -> dict:
    import base64
    token = base64.b64encode(f"{nip}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_tanpa_auth_tier_publik():
    """Tanpa kredensial -> tier PUBLIC (bukan 401): baca dokumen umum saja.

    Identitas yang diteruskan ke service adalah PUBLIC, BUKAN None. Itu yang
    membuatnya aman: PUBLIC -> sambungan non-pemilik tanpa unit -> RLS hanya
    umum. None akan memberi sambungan pemilik yang kebal RLS."""
    from ragcore.domain.users import PUBLIC

    client, ans, _, _ing = _client()
    r = client.post("/ask", json={"question": "q"})
    assert r.status_code == 200
    assert ans.seen["app_user"] is PUBLIC
    assert ans.seen["person"] is PUBLIC


def test_basic_auth_valid_meneruskan_user_ke_kedua_lapis():
    """NIP+sandi benar -> User yang sama mengisi app_user DAN person."""
    from ragcore.domain.users import REGISTRY

    client, ans, _, _ing = _client()
    # pakai NIP nyata dari REGISTRY + sandi lab
    nip = next(iter(REGISTRY))
    r = client.post("/ask", json={"question": "q"}, headers=_basic(nip, "lab2026"))
    assert r.status_code == 200
    assert ans.seen["app_user"] is REGISTRY[nip]
    assert ans.seen["person"] is REGISTRY[nip]


def test_basic_auth_salah_ditolak_401():
    client, ans, _, _ing = _client()
    r = client.post("/ask", json={"question": "q"},
                    headers=_basic("NCS-0012", "sandi-salah"))
    assert r.status_code == 401
    assert ans.seen is None      # service TIDAK dipanggil dengan kredensial salah


def test_agent_auth_diteruskan_sebagai_identity():
    from ragcore.domain.users import REGISTRY

    client, _, agt, _ing = _client()
    nip = next(iter(REGISTRY))
    r = client.post("/agent/ask", json={"question": "q"},
                    headers=_basic(nip, "lab2026"))
    assert r.status_code == 200
    assert agt.seen["identity"] is REGISTRY[nip]


def test_agent_publik_ditolak_401():
    """Agent punya tool basis data karyawan yang TIDAK ter-scope per orang.
    Baca dokumen boleh anonim (RLS menurunkannya ke umum), tapi jalur basis
    data WAJIB login - anonim (PUBLIC) ditolak sebelum service dipanggil."""
    client, _, agt, _ing = _client()
    r = client.post("/agent/ask",
                    json={"question": "tampilkan cuti semua karyawan"})
    assert r.status_code == 401
    assert agt.seen is None      # agent TIDAK dipanggil oleh PUBLIC


# --- unggah dokumen: unit dari user terautentikasi, bukan dari request ------

def test_upload_wajib_login_bukan_publik():
    """Baca boleh anonim, MENULIS tidak: PUBLIC ditolak 401 di /documents."""
    client, _, _, ing = _client()
    r = client.post("/documents", files={"file": ("x.pdf", b"data")})
    assert r.status_code == 401
    assert ing.seen is None      # service tidak dipanggil oleh PUBLIC


def test_upload_unit_dari_user_bukan_request():
    """Kritis: walau request TIDAK bisa mengirim unit, dokumen tetap ditandai
    unit pengunggah - diambil IngestService dari identitas, bukan dari form."""
    from ragcore.domain.users import REGISTRY

    client, _, _, ing = _client()
    nip = next(iter(REGISTRY))
    r = client.post("/documents", files={"file": ("SOP-baru.pdf", b"data")},
                    data={"kind": "sop", "classification": "umum"},
                    headers=_valid_auth())
    assert r.status_code == 201
    body = r.json()
    # unit di receipt = unit pengunggah, tidak pernah dikirim client
    assert body["unit"] == REGISTRY[nip].unit
    assert ing.seen["uploader"] is REGISTRY[nip]
    assert ing.seen["classification"] == "umum"
