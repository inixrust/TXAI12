"""Adapter HTTP di atas lapisan application — puncak diagram target.

Inilah pembuktian bahwa `FastAPI -> ChatService -> domain` benar-benar berdiri:
handler HTTP hanya MEMANGGIL use-case yang sudah ada dan mengirim hasil
to_payload()-nya sebagai JSON. NOL logika bisnis di sini, NOL akses langsung
ke Ollama/pgvector/MCP - semuanya lewat AnswerService dan AgentService.

Dibangun di atas Starlette, bukan FastAPI: Starlette sudah terpasang (fondasi
FastAPI), jadi tidak ada dependensi baru - sejalan dengan sisa lab ini. Pindah
ke FastAPI adalah drop-in: ASGI yang sama, pola yang sama, hanya menambah
model pydantic dan OpenAPI otomatis.

    from ragcore.api.http import build_api
    app = build_api()          # untuk uvicorn
    # uvicorn --factory ragcore.api.http:build_api

Service DISUNTIK lewat create_api(), jadi tes memakai fake tanpa Ollama maupun
Postgres - lihat test_api.py. Itu keuntungan langsung dari lapisan application
yang dependency-nya bisa ditukar.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=400)


class _AuthError(Exception):
    """Kredensial diberikan tapi salah - beda dari tidak diberikan sama sekali."""


def _resolve_identity(request: Request) -> Any:
    """Ubah header Authorization menjadi identitas.

    TIGA HASIL, DAN BEDANYA DISENGAJA:

      tanpa header   -> PUBLIC. Tier tanpa login: hanya dokumen umum, lewat
                        sambungan non-pemilik. AMAN karena PUBLIC != None -
                        None akan memberi sambungan pemilik yang kebal RLS.
      header salah   -> _AuthError (401). Kredensial yang keliru adalah
                        kesalahan yang harus disebut, BUKAN diam-diam
                        diturunkan ke publik - itu menyembunyikan bug klien.
      kredensial sah -> User. Akses penuh sesuai unit dan perannya.

    Fail-safe, bukan fail-closed penuh: yang lupa login mendapat tier paling
    sempit (umum), bukan ditolak. Yang SALAH login tetap ditolak.

    Basic auth memakai ulang login() yang ada; di produksi diganti token/OIDC
    dengan bentuk sama: kredensial -> User -> diteruskan ke service.
    """
    from ragcore.domain.login_guard import guarded_login
    from ragcore.domain.users import PUBLIC

    header = request.headers.get("authorization", "")
    if not header:
        return PUBLIC
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic":
        raise _AuthError("hanya Basic auth yang didukung")
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as e:
        raise _AuthError("kredensial Basic tidak bisa didekode") from e
    nip, _, password = decoded.partition(":")
    person, terkunci = guarded_login(nip, password)
    if terkunci:
        # Brute-force lock: tolak lebih dulu, tanpa membocorkan apakah sandinya
        # benar. Sama seperti UI - lockout per-NIP, di memori proses.
        raise _AuthError("terlalu banyak percobaan login, coba lagi nanti")
    if person is None:
        raise _AuthError("NIP atau sandi salah")
    return person


def create_api(answer_service: Any, agent_service: Any,
               ingest_service: Any = None) -> Starlette:
    """Rakit aplikasi HTTP dengan service yang DISUNTIK.

    Menerima service jadi, bukan membangunnya sendiri: produksi memberi yang
    nyata (lihat build_api), tes memberi yang palsu. Adapter ini tidak tahu
    apakah di baliknya ada Ollama atau tiruan - dan memang tidak perlu tahu.
    """

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def ask(request: Request) -> JSONResponse:
        """RAG langsung: dokumen -> jawaban tersitasi."""
        try:
            identity = _resolve_identity(request)
        except _AuthError as e:
            return JSONResponse({"error": str(e)}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return _bad_request("body harus JSON")
        if not isinstance(body, dict):
            return _bad_request("body harus objek JSON")   # [1], "hi" -> 400
        question = body.get("question")
        if not question:
            return _bad_request("field 'question' wajib diisi")

        # Identitas diteruskan ke KEDUA lapis: app_user (filter aplikasi) dan
        # person (RLS basis data). Service yang menegakkan; adapter hanya
        # meneruskan. Anonim tidak mungkin sampai sini - _resolve_identity
        # sudah menolaknya dengan 401.
        outcome = answer_service.ask(question, app_user=identity,
                                     person=identity, k=(body or {}).get("k"))
        return JSONResponse(outcome.to_payload())

    async def agent_ask(request: Request) -> JSONResponse:
        """Agent hibrida: dokumen + basis data lewat tool."""
        from ragcore.domain.users import PUBLIC

        try:
            identity = _resolve_identity(request)
        except _AuthError as e:
            return JSONResponse({"error": str(e)}, status_code=401)
        # Agent punya tool BASIS DATA karyawan yang tak ter-scope per orang.
        # Baca dokumen boleh anonim (RLS menurunkannya ke umum), tapi jalur
        # basis data WAJIB login - sama seperti unggah. Penjaga kedua ada di
        # tool itu sendiri (guard_db_access); ini menutup pintunya lebih dulu.
        if identity is PUBLIC:
            return JSONResponse(
                {"error": "agent basis data wajib login"}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return _bad_request("body harus JSON")
        if not isinstance(body, dict):
            return _bad_request("body harus objek JSON")   # [1], "hi" -> 400
        question = body.get("question")
        if not question:
            return _bad_request("field 'question' wajib diisi")

        outcome = await agent_service.ask_once(question, identity=identity)
        return JSONResponse(outcome.to_payload())

    async def submit_document(request: Request) -> JSONResponse:
        """Unggah dokumen ke antrean ingest (jalur TULIS).

        unit TIDAK diterima dari request - IngestService mengambilnya dari
        pengunggah yang terautentikasi. Klasifikasi boleh dipilih, tetapi
        service menggagal-tutupnya bila nilainya tak dikenal.
        """
        from ragcore import config
        from ragcore.domain.users import PUBLIC

        try:
            identity = _resolve_identity(request)
        except _AuthError as e:
            return JSONResponse({"error": str(e)}, status_code=401)
        # Menulis WAJIB login: PUBLIC tanpa unit menghasilkan dokumen yang
        # tak terlihat siapa pun (unit None + terbatas). Baca boleh anonim,
        # unggah tidak.
        if identity is PUBLIC:
            return JSONResponse(
                {"error": "unggah dokumen wajib login"}, status_code=401)

        # BATAS UKURAN DITEGAKKAN SEBELUM ISI DISERAP KE MEMORI. Membaca dulu
        # lalu mengecek panjangnya berarti berkas multi-GB sudah terlanjur
        # menghabiskan memori (dan request.form() menampung ke temp) sebelum
        # ditolak - vektor kehabisan sumber daya di jalur tulis.
        maks = int(config.MAX_UPLOAD_MB * 1024 * 1024)
        terlalu_besar = _bad_request(
            f"berkas melampaui batas {config.MAX_UPLOAD_MB:.0f} MB")
        # (a) Gerbang Content-Length: tolak yang jelas kelewat besar SEBELUM
        #     multipart di-parse. Slack 1 MB untuk batas boundary + field lain.
        panjang = request.headers.get("content-length", "")
        if panjang.isdigit() and int(panjang) > maks + 1024 * 1024:
            return terlalu_besar

        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return _bad_request("field berkas 'file' (multipart) wajib diisi")
        # (b) Baca TERBATAS: paling banyak maks+1 byte. Kalau lebih dari maks,
        #     berkasnya melampaui batas - ditolak tanpa membuffer sisanya.
        content = await upload.read(maks + 1)
        if len(content) > maks:
            return terlalu_besar

        try:
            receipt = ingest_service.submit(
                upload.filename, content, uploader=identity,
                kind=str(form.get("kind", "sop")),
                classification=str(form.get("classification", "terbatas")))
        except Exception as e:
            # blob.TooLarge dan sejenisnya -> 400, bukan 500: kesalahan
            # pengunggah, bukan kesalahan server.
            return _bad_request(str(e))
        return JSONResponse(receipt.to_payload(), status_code=201)

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/ask", ask, methods=["POST"]),
        Route("/agent/ask", agent_ask, methods=["POST"]),
    ]
    if ingest_service is not None:
        routes.append(Route("/documents", submit_document, methods=["POST"]))
    return Starlette(routes=routes)


def build_api() -> Starlette:
    """Rakit API dengan service produksi (Ollama, pgvector, MCP Oracle)."""
    from ragcore.application import (
        build_agent_service,
        build_answer_service,
        build_ingest_service,
    )

    return create_api(build_answer_service(), build_agent_service(),
                      build_ingest_service())
