"""Antarmuka web TX-AI12 — login, hak akses tertegakkan, penanda mutu ekstraksi.

    STORAGE=pgvector streamlit run apps/app12.py

Isinya ada di ragcore/ui/txai12.py; berkas ini hanya titik masuknya.
"""
from ragcore.settings.security import start_lease_renewer
from ragcore.ui.txai12 import run

# Jaga kredensial DB dinamis tetap segar (perpanjang/rotasi lease di latar).
# Tak berefek bila kredensial dinamis tak dipakai; aman dipanggil tiap rerun.
start_lease_renewer()

run()
