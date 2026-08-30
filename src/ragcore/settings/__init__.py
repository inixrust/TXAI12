"""Setelan aplikasi, dipecah menurut urusan.

Dulu semuanya di satu berkas `config.py` sepanjang 542 baris - satu modul
yang tahu segalanya, dan yang SEMUA subpaket bergantung padanya. Akibatnya
mengubah DPI VLM menyentuh berkas yang sama dengan logika rahasia kritis.

Sekarang tiap urusan punya modulnya sendiri:

    _env          membaca .env, helper flag        (fondasi, tanpa dependensi)
    paths         letak dokumen, indeks, cache
    security      mode produksi + kebijakan rahasia
    database      storage vektor + URL Postgres + GUC RLS
    mcp           server MCP Oracle + SQLcl
    models        model chat, embedding, reranker
    vision        VLM dan tuning DPI
    retrieval     chunking dan pencarian
    documents     kosakata status, ambang, batas unggah
    observability Langfuse

`ragcore.config` tetap ada sebagai FASAD yang mengekspor ulang semuanya,
jadi `from ragcore import config; config.MODEL_CHAT` tetap bekerja seperti
sebelumnya. Kode baru boleh mengimpor modul yang spesifik langsung -
`from ragcore.settings.security import IS_PRODUCTION` - dan hanya menarik
urusan yang benar-benar dipakainya.

.env dibaca DI SINI, di __init__ paket: Python menjalankan __init__ paket
sebelum submodul mana pun, jadi variabel lingkungan sudah termuat sebelum
satu pun modul setelan membaca os.getenv.
"""
from ragcore.settings._env import load_env

load_env()
