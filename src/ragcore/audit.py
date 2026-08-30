"""Jejak audit aktivitas user ke Langfuse — untuk debugging dan audit.

KEAMANAN LEBIH DULU, DAN ITU MEMBENTUK SELURUH MODUL INI. Audit yang mencatat
terlalu banyak berubah menjadi kebocoran: sandi, isi dokumen, atau PII yang
menumpuk di server jejak terbaca siapa pun yang punya akses ke sana - dan
justru karena datanya sensitif, orang memilih on-premise sejak awal. Empat
penjaga, dan urutannya disengaja dari yang paling kuat:

  1. ALLOWLIST field. HANYA nama field yang disebut di ALLOWED yang dicatat;
     apa pun di luar itu dibuang. Menambah field audit menjadi keputusan
     SADAR di berkas ini, bukan efek samping di tempat pemanggilan.

  2. DENYLIST substring sebagai lapis kedua. Field yang namanya mengandung
     'sandi'/'password'/'token'/'secret'/'isi' dibuang BAHKAN seandainya
     seseorang menambahkannya ke allowlist karena khilaf. Dua lapis, karena
     yang satu pasti suatu saat bocor.

  3. Nilai DIPANGKAS. Audit mencatat FAKTA aktivitas - siapa, apa, kapan,
     hasilnya - bukan muatannya. String panjang dipotong.

  4. FAIL-SAFE. Server jejak yang mati TIDAK boleh menggagalkan aksi user.
     Audit adalah pengamatan, bukan prasyarat berjalannya sistem.

Identitas yang dicatat: NIP (bukan nama), unit, peran - konsisten dengan
tracing.py. Sandi yang dicoba saat login GAGAL tidak pernah masuk sini; yang
dicatat hanya NIP yang dicoba, karena itulah yang berguna untuk mendeteksi
percobaan paksa - dan itu bukan rahasia.
"""
from __future__ import annotations

from . import config
from .log import get_logger
from .tracing import callback_handler, trace_identity

log = get_logger(__name__)

# Field yang BOLEH dicatat. Semuanya tentang KONTEKS aktivitas, bukan muatan.
# Menambah di sini adalah keputusan sadar - tinjau apakah nilainya bisa memuat
# rahasia atau PII sebelum menambahkannya.
ALLOWED = frozenset({
    "unit", "peran", "berkas", "jenis", "klasifikasi", "alasan",
    "jumlah", "sumber", "target_nip", "durasi_ms",
})

# Lapis kedua: nama field yang mencurigakan SELALU dibuang, apa pun allowlist.
_DENY_SUBSTR = ("sandi", "password", "passwd", "token", "secret", "rahasia",
                "isi", "content", "credential", "kunci", "key")

# Panjang maksimum nilai string yang dicatat. Audit bukan tempat menyimpan teks.
_MAX = 200


def _safe_fields(fields: dict) -> dict:
    """Saring field: allowlist dulu, lalu denylist, lalu pangkas nilai."""
    out: dict = {}
    for k, v in fields.items():
        if v is None:
            continue
        if k not in ALLOWED:
            log.debug("audit: field '%s' dibuang (di luar allowlist)", k)
            continue
        if any(s in k.lower() for s in _DENY_SUBSTR):
            log.debug("audit: field '%s' dibuang (denylist)", k)
            continue
        if isinstance(v, str) and len(v) > _MAX:
            v = v[:_MAX] + "…"
        out[k] = v
    return out


def record(action: str, person=None, *, subject: str | None = None,
           outcome: str | None = None, session: str | None = None,
           **fields) -> None:
    """Catat satu aktivitas user sebagai event audit. Fail-safe, security-first.

    action  : verba pendek - 'login', 'login-gagal', 'tamu-masuk', 'keluar',
              'unggah', 'unggah-ditolak', 'tanya'.
    person  : User/PUBLIC/None yang melakukan; NIP diambil darinya.
    subject : NIP mentah bila tak ada objek person - dipakai untuk login GAGAL,
              di mana kita tahu NIP yang DICOBA tapi belum tentu ada User-nya.
              JANGAN pernah mengoper sandi ke sini.
    outcome : ringkas hasil ('berhasil'/'ditolak'/'antre'/...).
    session : id sesi web bila ada, supaya aktivitas satu sesi berdampingan.
    **fields: konteks tambahan - HANYA yang ada di ALLOWED yang lolos.
    """
    if not config.USE_TRACING:
        return
    try:
        # Memastikan host env + klien siap lewat jalur yang sudah dikeraskan
        # (mencegah trace lari ke cloud - lihat tracing.callback_handler).
        callback_handler()
        from langfuse import get_client

        nip = trace_identity(person) or subject or "anon"
        meta: dict = {
            "langfuse_user_id": nip,
            "langfuse_tags": ["audit", action],
        }
        if session:
            meta["langfuse_session_id"] = str(session)
        if person is not None:
            unit = getattr(person, "unit", None)
            peran = getattr(person, "role", None) or getattr(person, "peran", None)
            if unit:
                meta["unit"] = unit
            if peran:
                meta["peran"] = peran
        meta.update(_safe_fields(fields))

        get_client().create_event(
            name=f"audit:{action}",
            input={"aksi": action, "nip": nip},
            output={"hasil": outcome} if outcome else None,
            metadata=meta,
        )
    except Exception as e:
        # Audit yang gagal tidak boleh menjatuhkan aksi user. Dicatat di level
        # debug supaya bisa didiagnosis tanpa membanjiri log.
        log.debug("audit '%s' dilewati (%s: %s)", action, type(e).__name__, e)
