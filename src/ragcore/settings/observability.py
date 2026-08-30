"""Langfuse: pengiriman trace, dengan jalur mati yang aman.

Observability TIDAK boleh menjadi prasyarat agar aplikasi bisa hidup. Kalau
kunci Langfuse kosong, tracing mati dan sistem berjalan normal - itu keputusan
yang ditegakkan di sini lewat USE_TRACING, bukan sekadar diharapkan.
"""
from __future__ import annotations

import os

# Kosongkan salah satu kunci untuk mematikan pengiriman tracing. Sistem tetap
# berjalan normal tanpa Langfuse — observability tidak boleh menjadi
# prasyarat agar aplikasi bisa hidup.
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
USE_TRACING: bool = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
