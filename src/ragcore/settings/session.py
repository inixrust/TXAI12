"""Setelan sesi login web: rahasia penanda-tangan + masa berlaku + nama cookie.

Sesi bertahan lintas-refresh lewat cookie berisi token yang DITANDATANGANI
(HMAC). Rahasianya di sini yang membuat token tak bisa dipalsukan - tanpa itu,
menyimpan NIP di cookie hanyalah "silakan mengaku jadi siapa saja".
"""
from __future__ import annotations

import os

from ragcore.settings.security import signing_secret

# Rahasia HMAC untuk token sesi. Default HANYA untuk lab; di RAG_ENV=production
# WAJIB disetel lewat environment (lihat signing_secret()).
SESSION_SECRET: str = signing_secret("SESSION_SECRET", "lab-txai12-session-2026")

# Masa berlaku token (detik). Bawaan 1 jam - setelah itu wajib login ulang.
SESSION_TTL: int = int(os.getenv("SESSION_TTL", "3600"))

# Nama cookie di browser. Berawalan agar tak bentrok dengan cookie Streamlit.
SESSION_COOKIE: str = os.getenv("SESSION_COOKIE", "sesi_txai12")
