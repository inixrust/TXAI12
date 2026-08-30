"""Evaluasi: mengubah 'rasanya lebih baik' menjadi angka yang bisa dibandingkan.

    set_uji  membaca dan menyaring kasus uji
    metrik   recall retrieval, kebocoran dokumen dicabut, kemampuan menolak

Evaluasi retrieval sengaja TIDAK memanggil model bahasa: cepat, murah,
objektif, dan bisa dijalankan setiap kali ada perubahan setelan.
"""
from __future__ import annotations

from .metrics import (
    compare_methods,
    evaluate_refusal,
    evaluate_retrieval,
    evaluate_status_filter,
    recall_curve,
)
from .testset import (
    TestCase,
    load_testset,
    refusal_cases,
    retrieval_cases,
    version_cases,
)

__all__ = [
    "TestCase",
    "annotations",
    "compare_methods",
    "evaluate_refusal",
    "evaluate_retrieval",
    "evaluate_status_filter",
    "load_testset",
    "recall_curve",
    "refusal_cases",
    "retrieval_cases",
    "version_cases",
]
