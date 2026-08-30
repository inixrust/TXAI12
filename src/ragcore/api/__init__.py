"""Adapter HTTP (Starlette/ASGI) di atas lapisan application.

Sejajar dengan commands/ (CLI) dan ui/ (Streamlit): satu lagi cara memanggil
use-case yang sama, tanpa menduplikasi logikanya. Lihat http.py.
"""
from ragcore.api.http import build_api, create_api

__all__ = ["build_api", "create_api"]
