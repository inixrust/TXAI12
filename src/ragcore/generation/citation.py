"""Pemeriksaan citation: murah, otomatis, dan sadar diri akan batasnya.

Yang diperiksa di sini hanya STRUKTUR — apakah penanda sumbernya ada dan
menunjuk chunks yang benar-benar dikirim. Pemeriksaan ini TIDAK menangkap
citation yang menunjuk chunks nyata namun isinya tak mendukung klaim; lihat
pembahasan halusinasi with_citation di modul B5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config

# Pola satu penanda citation. Menerima bentuk gabungan seperti [1, 2] atau [1;2],
# bukan hanya [1] — kalau tidak, kalimat ber-citation ganda dianggap tak bersumber
# dan cakupan terhitung rendah keliru. Wajib memuat setidaknya satu digit.
CITATION_PATTERN = r"\[\s*\d[\d,;\s]*\]"

# Akhir kalimat: titik, tanda tanya, atau tanda seru yang diikuti spasi.
SENTENCE_PATTERN = r"(?<=[.!?])\s+"


@dataclass(frozen=True)
class CitationReport:
    """Hasil pemeriksaan struktural satu jawaban.

    hantu   nomor citation yang menunjuk chunks tak ada (terurut)
    cakupan bagian kalimat yang membawa citation, 0.0 sampai 1.0
    """

    hantu: tuple[int, ...]
    coverage: float

    @property
    def low_coverage(self) -> bool:
        return self.coverage < config.COVERAGE_THRESHOLD


def check_citation(answer_text: str, chunk_count: int) -> CitationReport:
    """Hitung citation hantu dan cakupan citation sebuah jawaban."""
    dirujuk: set[int] = set()
    for grup in re.findall(CITATION_PATTERN, answer_text):
        dirujuk.update(int(n) for n in re.findall(r"\d+", grup))
    hantu = tuple(sorted(n for n in dirujuk if not 1 <= n <= chunk_count))

    sentence = [k for k in re.split(SENTENCE_PATTERN, answer_text) if k.strip()]
    with_citation = [k for k in sentence if re.search(CITATION_PATTERN, k)]
    coverage = len(with_citation) / len(sentence) if sentence else 0.0

    return CitationReport(hantu=hantu, coverage=round(coverage, 2))


def citation_warnings(report: CitationReport, answer_text: str) -> list[str]:
    """Kalimat peringatan yang layak ditampilkan, atau daftar kosong.

    Dipisah dari pencetakan supaya baris peringatan yang sama bisa dipakai di
    baris perintah maupun di ui Streamlit.
    """
    message: list[str] = []
    if report.hantu:
        message.append(
            f"PERINGATAN: sitasi menunjuk potongan yang tidak ada: "
            f"{list(report.hantu)}"
        )
    # Penolakan memang tidak perlu citation — jangan diperingatkan.
    if config.NOT_FOUND not in answer_text and report.low_coverage:
        message.append(f"PERINGATAN: cakupan sitasi rendah ({report.coverage:.0%})")
    return message
