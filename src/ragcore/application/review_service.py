"""Antrean & keputusan tinjauan alur Konsultasi - DI LAPIS APLIKASI, bukan UI.

DUA HAL YANG DIPINDAHKAN KE SINI, DAN KENAPA.

1. PENEGAKAN DI TITIK RESUME, BUKAN DI UI. Alur Konsultasi (flow/production.py)
   menahan vonis kepatuhan untuk disetujui manusia (interrupt LangGraph).
   Menyembunyikan tombol di UI TIDAK cukup - itu kosmetik: siapa pun yang bisa
   memanggil resume bisa mengesahkan vonis. Penegakan yang sebenarnya ada DI
   SINI: apply_decision() memverifikasi peran peninjau DAN bahwa ia BUKAN
   pemohon, SEBELUM graf dilanjutkan. Kalau ini kelak diekspos sebagai endpoint
   HTTP, endpoint itu cukup memanggil apply_decision() - gerbangnya satu, di
   lapis aplikasi, bukan tersebar di presentasi.

2. ANTREAN DARI POSTGRES, BUKAN SESI BROWSER. Keadaan tertunda dulu hidup di
   st.session_state - hilang saat pindah peramban, dan tak terlihat peninjau
   lain. Di sini ia baris di tabel flow_reviews (Postgres yang SAMA dengan
   checkpointer). Peninjau mana pun, dari sesi mana pun, melihat antrean yang
   sama; thread_id menautkan baris ke checkpointer untuk resume.

Tabel ini hanya INDEKS yang bisa dibaca manusia (pertanyaan, pemohon, alasan) +
status. Kebenaran keadaan graf tetap di checkpointer; thread_id perekatnya.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg

from ragcore import config
from ragcore.domain.users import is_reviewer


class ReviewDenied(Exception):
    """Keputusan ditolak: bukan peninjau berwenang, atau pemohon sendiri."""


_DDL = """
CREATE TABLE IF NOT EXISTS flow_reviews (
  thread_id       TEXT PRIMARY KEY,
  requester_nip   TEXT NOT NULL,
  requester_name  TEXT,
  question        TEXT,
  answer_text     TEXT,
  hold_reason     TEXT,
  coverage        REAL,
  source          TEXT,
  status          TEXT NOT NULL DEFAULT 'pending',
  decided_by      TEXT,
  decided_by_name TEXT,
  note            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at      TIMESTAMPTZ
);
"""

_COLS = ("thread_id, requester_nip, requester_name, question, answer_text, "
         "hold_reason, coverage, source, status, decided_by_name, note")


@dataclass(frozen=True)
class Review:
    thread_id: str
    requester_nip: str
    requester_name: str
    question: str
    answer_text: str
    hold_reason: str
    coverage: float
    source: str
    status: str
    decided_by_name: str
    note: str


def _connect():
    return psycopg.connect(config.PG_URL_DIRECT)


def setup() -> None:
    """Buat tabel bila belum ada. Idempoten; dipanggil malas oleh fungsi lain."""
    with _connect() as conn:
        conn.execute(_DDL)


# --------------------------------------------------------------- gerbang

def authorize(reviewer: object, requester_nip: str) -> str | None:
    """None bila BOLEH memutuskan; kalimat penolakan bila tidak.

    Fungsi MURNI - inti pemisahan tugas, dapat diuji tanpa basis data:
      1. hanya peninjau berwenang (pimpinan Divisi SDM atau Direksi), dan
      2. BUKAN si pemohon (yang meminta vonis tak boleh mengesahkan vonisnya).
    """
    if not is_reviewer(reviewer):
        return ("Hanya peninjau berwenang (pimpinan Divisi SDM atau Direksi) "
                "yang dapat memutuskan vonis kepatuhan.")
    if getattr(reviewer, "nip", None) == requester_nip:
        return "Pemohon tidak boleh menyetujui vonisnya sendiri."
    return None


# --------------------------------------------------------------- antrean

def record_hold(thread_id: str, requester: object, payload: dict) -> None:
    """Catat/segarkan satu tinjauan tertunda ke antrean (upsert per thread)."""
    setup()
    src = ", ".join(dict.fromkeys(
        s for s in (payload.get("source") or []) if s))
    with _connect() as conn:
        conn.execute(
            """INSERT INTO flow_reviews
                 (thread_id, requester_nip, requester_name, question,
                  answer_text, hold_reason, coverage, source, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending')
               ON CONFLICT (thread_id) DO UPDATE SET
                 answer_text = EXCLUDED.answer_text,
                 hold_reason = EXCLUDED.hold_reason,
                 coverage    = EXCLUDED.coverage,
                 source      = EXCLUDED.source,
                 status      = 'pending'""",
            (thread_id, getattr(requester, "nip", ""),
             getattr(requester, "name", ""), payload.get("question"),
             payload.get("answer_text"), payload.get("hold_reason"),
             float(payload.get("citation_coverage") or 0), src))


def _rows(where: str, args: tuple) -> list[Review]:
    setup()
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {_COLS} FROM flow_reviews {where}", args).fetchall()
    return [Review(*r) for r in rows]


def pending() -> list[Review]:
    """Semua tinjauan yang MASIH menunggu - inbox bagi peninjau."""
    return _rows("WHERE status = 'pending' ORDER BY created_at", ())


def own(nip: str) -> list[Review]:
    """Tinjauan milik pemohon ini (menunggu atau baru diputuskan), agar ia
    melihat status & hasilnya meski bukan peninjau."""
    return _rows(
        "WHERE requester_nip = %s ORDER BY created_at DESC LIMIT 5", (nip,))


def apply_decision(thread_id: str, reviewer: object, action: str,
                   note: str = "") -> dict:
    """GERBANG OTORITATIF + resume graf. Ini titik penegakan yang sebenarnya.

    Menolak (ReviewDenied) bila peninjau tak berwenang atau ia si pemohon -
    APA PUN yang ditampilkan UI, dan SEBELUM graf disentuh. Baru setelah lolos,
    graf dilanjutkan lewat flow.run_flow(Command(resume=...)) dan barisnya
    ditandai diputuskan. Kembalikan state akhir graf.
    """
    from langgraph.types import Command

    from ragcore.flow import run_flow

    setup()
    with _connect() as conn:
        row = conn.execute(
            "SELECT requester_nip, status FROM flow_reviews WHERE thread_id = %s",
            (thread_id,)).fetchone()
    if row is None or row[1] != "pending":
        raise ReviewDenied("Tinjauan tidak ditemukan atau sudah diputuskan.")

    tolak = authorize(reviewer, row[0])
    if tolak:
        raise ReviewDenied(tolak)

    result = run_flow(Command(resume={"action": action, "note": note}),
                      thread_id)

    with _connect() as conn:
        conn.execute(
            """UPDATE flow_reviews SET status = %s, decided_by = %s,
                 decided_by_name = %s, note = %s, answer_text = %s,
                 decided_at = now() WHERE thread_id = %s""",
            (result.get("status") or action, getattr(reviewer, "nip", ""),
             getattr(reviewer, "name", ""), note, result.get("answer_text"),
             thread_id))
    return result
