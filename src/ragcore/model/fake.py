"""Jalur cadangan bila Ollama bermasalah di tengah kelas.

Mutunya buruk dengan sengaja. Yang dijaga di sini bukan mutu jawaban,
melainkan agar SELURUH ALUR tetap berjalan: peserta yang Ollama-nya bermasalah
masih bisa mengikuti pelajaran tentang chunking, metadata, dan evaluasi.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from .. import config


class FakeEmbedding:
    """Embedding palsu berbasis hash. HANYA untuk berjaga-jaga.

    Ia tidak memahami makna sama sekali, hanya mengubah kata menjadi angka
    secara deterministik.

    Justru berguna sebagai bahan ajar: bandingkan angka recall-nya dengan
    bge-m3, dan peserta melihat sendiri berapa besar sumbangan embedding yang
    benar-benar memahami bahasa.
    """

    DIM = 256

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.DIM
        word = "".join(c.lower() if c.isalnum() else " " for c in text).split()
        for k in word:
            fingerprint = int(hashlib.md5(k.encode()).hexdigest(), 16)
            vector[fingerprint % self.DIM] += 1.0
        length = sum(x * x for x in vector) ** 0.5 or 1.0
        return [x / length for x in vector]

    def embed_documents(self, listing: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in listing]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeReply:
    """Meniru bentuk balasan LangChain secukupnya: hanya `.content`."""

    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    """Model chat palsu. Tidak merangkai jawaban, hanya mengakui keadaannya.

    Sengaja TIDAK punya `bind_tools`: agent memang tidak bisa berjalan tanpa
    model sungguhan, dan lingkaran agent memeriksa hal itu untuk memberi pesan
    yang jelas alih-alih gagal di tengah jalan.
    """

    def invoke(self, user_input: Any) -> FakeReply:
        text = str(user_input)
        if "KONTEKS:" in text and len(text) > 200:
            return FakeReply(
                "[MODE TIRUAN] Model bahasa tidak aktif, jadi jawaban tidak "
                "dirangkai. Potongan yang berhasil diambil sudah ditampilkan "
                "di atas — itulah yang penting untuk pelajaran ini. [1]"
            )
        return FakeReply("[MODE TIRUAN]")


def is_active() -> bool:
    """Apakah lab sedang berjalan dengan model tiruan?"""
    return config.FAKE_MODE
