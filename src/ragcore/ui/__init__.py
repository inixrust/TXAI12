"""Lapisan presentasi web (Streamlit).

    txai12    antarmuka TX-AI12 - login, RLS tertegakkan, penanda mutu ekstraksi
    citations penampil dokumen ASLI di balik sitasi (verifikasi ke sumber)

Terpisah dari inti dengan sengaja: kode presentasi mengimpor dari lapisan di
bawahnya (generation, domain, ingest), tidak pernah sebaliknya. `display.py`
di root SENGAJA tidak di sini - ia format terminal yang dipakai juga oleh
generation dan commands, jadi menaruhnya di ui/ akan membalik arah itu.
"""
