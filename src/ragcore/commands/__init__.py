"""Titik masuk baris perintah.

Setiap modul di sini punya satu fungsi `utama(argv=None) -> int` yang memuat
seluruh urusan baris perintah: penguraian argumen, pencetakan, dan kode keluar.
Berkas di `src/` hanya memanggilnya, sehingga perintah di PANDUAN-PESERTA.md
tetap sama persis:

    python check.py            python search.py "pertanyaan"
    python -m ragcore.commands.load
    python -m ragcore.commands.index
    python -m ragcore.commands.answer "pertanyaan"
    python -m ragcore.commands.evaluate
    python agent.py "..."     streamlit run app.py

Bentuk `python -m ragcore.commands.search "pertanyaan"` juga berjalan.
"""
