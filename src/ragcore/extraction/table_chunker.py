"""Pemotongan yang sadar tabel (L4).

Masalahnya khas hasil VLM. Prompt ekstraksi meminta model menuliskan tabel
sebagai tabel Markdown, jadi halaman pindaian yang bertabel menghasilkan
blok baris berpipa yang panjang. Pemotong biasa memenggalnya di tengah:

    chunks 1 | Nilai Pengadaan        | Metode              | Penyetuju     |
               | Sampai Rp 10.000.000   | Pembelian langsung  | Kepala Unit   |
               | Rp 10.000.001 - 100 jt | Permintaan penawaran| Kepala Divisi |

    chunks 2 | Rp 100.000.001 - 500 jt| Seleksi terbatas    | Dir. Keuangan |
               | Di atas Rp 500.000.000 | Seleksi terbuka     | Dir. Utama    |

Potongan kedua masih memuat angkanya, tetapi tidak lagi memuat judul
kolomnya. "Rp 100.000.001 - 500 jt" tanpa "Nilai Pengadaan" di atasnya
tidak berarti apa-apa - dan yang lebih buruk, model yang membacanya akan
tetap menjawab dengan percaya diri.

Aturannya cuma dua:

  1. Blok tabel tidak dipotong selama masih muat.
  2. Kalau terpaksa dipotong, ULANGI barisan judulnya di tiap pecahan.
"""
from __future__ import annotations

import re

from ragcore import config

# Baris tabel Markdown: diawali dan diakhiri batang tegak.
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

# Baris pemisah judul: | --- | :---: | dan ragamnya.
SEPARATOR_ROW = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def group_by(row: list[str]) -> list[tuple[str, list[str]]]:
    """Pisahkan teks menjadi blok 'tabel' dan 'teks' secara berurutan.

    Sederhana dan sengaja begitu: prompt L3 sudah meminta VLM menuliskan
    tabel dalam bentuk pipa, jadi pengenalannya tidak perlu rumit. Pemotong
    yang mencoba menebak tabel dari tata letak spasi akan salah lebih sering
    daripada benar.
    """
    blok: list[tuple[str, list[str]]] = []
    current: list[str] = []
    kind: str | None = None

    for b in row:
        j = "tabel" if TABLE_ROW.match(b) else "teks"
        if j != kind and current:
            blok.append((kind, current))
            current = []
        kind = j
        current.append(b)

    if current:
        blok.append((kind, current))
    return blok


def _heading_sequence(row: list[str]) -> list[str]:
    """Kembalikan baris judul tabel: baris pertama, plus pemisah bila ada.

    Tabel Markdown yang benar punya dua: judul dan pemisah. Keluaran VLM
    tidak selalu menyertakan pemisahnya, jadi jangan mengandaikannya ada.
    """
    if len(row) >= 2 and SEPARATOR_ROW.match(row[1]):
        return row[:2]
    return row[:1]


def _split_table(row: list[str], limit: int) -> list[str]:
    """Potong satu blok tabel, mengulang judulnya di setiap pecahan."""
    title = _heading_sequence(row)
    content = row[len(title):]

    result: list[str] = []
    current = list(title)

    for b in content:
        candidate_length = len("\n".join(current)) + len(b) + 1
        if candidate_length > limit and len(current) > len(title):
            result.append("\n".join(current))
            current = list(title)      # judul diulang, bukan dibuang
        current.append(b)

    if len(current) > len(title):
        result.append("\n".join(current))
    return result


def _split_text(text: str, limit: int) -> list[str]:
    """Potong blok non-tabel di batas paragraf, lalu baris, lalu paksa."""
    if len(text) <= limit:
        return [text]

    result: list[str] = []
    current = ""
    for paragraf in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraf}" if current else paragraf
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            result.append(current)
        # Satu paragraf yang sendirian sudah melebihi batas: potong per baris.
        if len(paragraf) <= limit:
            current = paragraf
        else:
            current = ""
            for b in paragraf.splitlines():
                candidate = f"{current}\n{b}" if current else b
                if len(candidate) <= limit or not current:
                    current = candidate
                else:
                    result.append(current)
                    current = b
    if current:
        result.append(current)
    return result


# Baris yang MENAMAI sebuah tabel: judul pasal, atau kalimat pengantar yang
# berakhir dengan titik dua.
_TITLE_PATTERN = re.compile(r"^(BAB|Pasal|Lampiran|Tabel)\b", re.IGNORECASE)


def table_caption(text_row: list[str], maximum: int = 2) -> list[str]:
    """Baris dari blok teks sebelumnya yang MENAMAI tabel sesudahnya.

    KENAPA TABEL PERLU MEMBAWA JUDULNYA. Pemotong ini menjadikan setiap tabel
    sebuah chunks tersendiri, sehingga judul kolomnya ikut utuh. Yang TIDAK
    ikut adalah judul pasal yang menerangkan tabel itu tabel APA - dan judul
    kolom saja tidak cukup membedakannya.

    Terbukti di lab ini. Satu halaman SE-12 memuat DUA tabel berstruktur
    nyaris sama:

        Pasal 3 - Uang Harian
        | Golongan | Dalam Provinsi | Luar Provinsi | ...
        | Manager  | Rp 350.000     | Rp 550.000    | ...

        Pasal 4 - Penginapan dan Transportasi
        | Golongan | Dalam Provinsi | Luar Provinsi |
        | Manager  | Rp 750.000     | Rp 1.000.000  |

    Tanpa judul pasalnya, kedua chunks itu TIDAK DAPAT DIBEDAKAN - oleh
    model maupun oleh manusia. Ditanya uang harian Manajer ke luar provinsi,
    agent mengambil tabel PENGINAPAN dan menjawab "Rp 1.000.000", lengkap
    dengan citation dokumen dan nomor halaman yang BENAR.

    Itulah bentuk kegagalan paling berbahaya di lab ini: angkanya nyata,
    sumbernya nyata, halamannya nyata, dan jawabannya salah. Tidak ada satu
    pun errors, dan tidak ada yang terlihat ragu.
    """
    candidate = [b.strip() for b in text_row if b.strip()][-maximum:]
    return [b for b in candidate if _TITLE_PATTERN.match(b) or b.endswith(":")]


def chunk_table_aware(text: str, limit: int | None = None) -> list[str]:
    """Potong teks hasil ekstraksi tanpa memisahkan tabel dari judul kolomnya.

    Kembalikan daftar chunks siap indeks.
    """
    limit = limit or config.CHUNK_SIZE
    result: list[str] = []

    title: list[str] = []
    for kind, row in group_by(text.splitlines()):
        utuh = "\n".join(row)

        if not utuh.strip():
            continue

        if kind == "tabel":
            # Judul dari blok teks TEPAT SEBELUMNYA dibawa masuk ke
            # setiap chunks tabel. Lihat table_caption().
            section = ([utuh] if len(utuh) <= limit
                      else _split_table(row, limit))
            prefix = "\n".join(title) + "\n" if title else ""
            result.extend(prefix + bg for bg in section)
        elif len(utuh) <= limit:
            result.append(utuh)
            title = table_caption(row)
        else:
            result.extend(_split_text(utuh, limit))
            title = table_caption(row)

    return result


def chunk_documents(page: list, limit: int | None = None) -> list:
    """Terapkan chunk_table_aware ke daftar Document, metadata dibawa serta.

    Hanya halaman hasil VLM yang lewat sini. Halaman ber-lapisan teks tetap
    memakai pemotong TX-AI11, karena tabelnya sudah berupa teks biasa dan
    penanda pasal jauh lebih berguna sebagai batas potong.
    """
    from ragcore.domain import Document

    keluar: list[Document] = []
    for h in page:
        if h.metadata.get("ekstraksi") != "vlm":
            keluar.append(h)
            continue
        for i, section in enumerate(chunk_table_aware(h.page_content, limit)):
            meta = dict(h.metadata)
            meta["potongan_ke"] = i
            meta["sadar_tabel"] = True
            keluar.append(Document(page_content=section, metadata=meta))
    return keluar
