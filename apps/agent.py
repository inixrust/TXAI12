"""Agent minimal, sepenuhnya on-premise — modul A2 / A6.

    python apps/agent.py "Saya dinas 3 hari golongan Manajer, berapa total uang hariannya?"
    python apps/agent.py "Berapa panjang minimum kata sandi sistem internal?"

Isinya ada di ragcore/agen/; berkas ini hanya titik masuknya.
"""
import sys

from ragcore.commands.agent import main

if __name__ == "__main__":
    sys.exit(main())
