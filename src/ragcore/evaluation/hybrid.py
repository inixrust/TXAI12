"""Dua metrik untuk sistem dua sumber (L9 lanjutan).

  ketepatan_alat    - apakah tool yang WAJIB dipanggil benar-benar dipanggil
  ketepatan_jawaban - apakah isinya cocok dengan acuan

Kenapa dipisah? Karena satu angka gabungan membuang persis informasi yang
dibutuhkan untuk memperbaiki. Bacalah selisih keduanya:

  alat tinggi, jawaban rendah  -> pemilihan sumbernya benar, penalarannya
                                  yang gagal. Perbaiki prompt penyusunan
                                  jawaban, bukan deskripsi tool.
  alat rendah, jawaban tinggi  -> jawaban benar karena kebetulan, atau
                                  karena model menghafal dari konteks lain.
                                  Ini yang paling berbahaya: terlihat
                                  berhasil, tidak akan bertahan.
  keduanya rendah              -> deskripsi tool. Mulai dari sana.

Set ujinya berkas nyata, bukan daftar di dalam kode: testset_hybrid.json
berisi 30 kasus dalam 12 jenis. Selain pemilihan sumber, ia menguji
pengecualian, aritmetika tanggal, agregat lintas view, HAK AKSES per
users, dan ketahanan terhadap injeksi. Lihat README bagian
"Set uji hibrida".
"""
from __future__ import annotations

import json

from ragcore import config
from ragcore.domain.users import REGISTRY

TEST_SET = json.loads(config.HYBRID_TEST_SET.read_text(encoding="utf-8"))

# Nama tool MCP Oracle berbeda-beda antarversi SQLcl, jadi pencocokannya
# longgar: cukup chunks kata yang menandai jenis tool-nya. Mengunci nama
# persis akan membuat evaluasi ini rusak setiap kali SQLcl diperbarui -
# dan rusaknya senyap, berupa skor nol yang terlihat seperti kegagalan model.
TOOL_HINT = {
    "search_rules": ("ketentuan", "documents", "sop"),
    "tanya_basis_data": ("sql", "query", "oracle", "database", "run-sql"),
}


def tools_called(message_message) -> set[str]:
    """Kumpulkan nama tool yang benar-benar dipanggil agent."""
    used = set()
    for p in message_message:
        for call in getattr(p, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else None
            if name:
                used.add(name.lower())
    return used


def case_user(case: dict):
    """Pengguna yang mengajukan pertanyaan, bila kasusnya menentukan.

    Kasus hak akses tidak bisa dinilai tanpa ini: pertanyaan yang sama
    punya jawaban benar yang BERBEDA tergantung siapa yang bertanya.
    """
    nip = case.get("pengguna")
    if not nip:
        return None

    return REGISTRY.get(nip)


def tools_correct(case: dict, used: set[str]) -> bool:
    """Apakah pemilihan tool untuk satu kasus sudah benar?

    Untuk kasus penolakan, alat_benar kosong. Agent BOLEH mencoba sekali
    lalu menyerah - itu perilaku yang wajar dan tidak dihitung salah.
    Yang salah adalah memanggil banyak tool berturut-turut untuk sesuatu
    yang memang tidak ada di kedua sumber.
    """
    required = case.get("alat_benar") or []
    if not required:
        return len(used) <= 1

    for w in required:
        # Nama kanoniknya selalu ikut: sebuah tool harus cocok dengan
        # namanya sendiri, tidak hanya dengan petunjuk longgarnya.
        hint = (w.lower(), *TOOL_HINT.get(w, ()))
        if not any(p in n for n in used for p in hint):
            return False
    return True

# Penilaian dan pelaporan kini punya modulnya sendiri, tetapi tetap diekspor
# dari sini: `from ragcore.evaluation import hybrid as evaluation` dipakai
# di commands/ dan di materi, dan memecah modul tidak boleh ikut memecah
# antarmuka yang sudah diajarkan.
#
# scoring bisa diimpor eager: ia tidak mengimpor balik modul ini.
# __all__ WAJIB ada di bawah. Tanpanya `ruff --fix` menghapus baris-baris ini
# sebagai impor tak terpakai — dan itu benar-benar terjadi saat modul ini
# dipecah: ERROR_PREFIX lenyap, dan yang memberi tahu hanya tes.
# reporting TIDAK boleh diimpor eager di sini: ia mengimpor balik tools_called
# dan tools_correct dari modul ini, jadi impor eager membentuk siklus yang
# pecah bergantung pada urutan - `import reporting` lebih dulu meledak,
# `import hybrid` lebih dulu selamat. Re-export malas lewat __getattr__
# memutus siklus itu tanpa mengubah antarmuka: evaluation.report tetap ada.
#
# Blok TYPE_CHECKING hanya dibaca type checker & linter, tidak dijalankan -
# jadi nama-nama ini terlihat oleh alat statis (dan __all__ di bawah sah di
# mata ruff) tanpa membangunkan siklus impor saat runtime.
from typing import TYPE_CHECKING  # noqa: E402

from ragcore.evaluation.scoring import (  # noqa: E402
    ERROR_PREFIX,
    REFUSES_KIND,
    SKIP_LIMIT,
    degenerate_output,
    fabricated_citation,
    known_codes,
    known_documents,
    matches_reference,
    refuses_correctly,
    score_answer,
    unusable_result,
    violates_forbidden,
)

if TYPE_CHECKING:
    from ragcore.evaluation.reporting import (
        HISTORY,
        compare_runs,
        report,
    )

_LAZY_FROM_REPORTING = {"HISTORY", "compare_runs", "report"}


def __getattr__(name: str):
    if name in _LAZY_FROM_REPORTING:
        from ragcore.evaluation import reporting
        return getattr(reporting, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ERROR_PREFIX",
    "HISTORY",
    "REFUSES_KIND",
    "SKIP_LIMIT",
    "TEST_SET",
    "TOOL_HINT",
    "case_user",
    "compare_runs",
    "degenerate_output",
    "fabricated_citation",
    "known_codes",
    "known_documents",
    "matches_reference",
    "refuses_correctly",
    "report",
    "score_answer",
    "tools_called",
    "tools_correct",
    "unusable_result",
    "violates_forbidden",
]
