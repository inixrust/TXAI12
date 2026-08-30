"""Perencanaan capacity (L13).

Tiga pertanyaan yang pasti diajukan atasan, dan semuanya harus dijawab
dengan angka dari MESIN ANDA SENDIRI:

  1. Berapa lama mengindeks seluruh arsip?
  2. Berapa besar penyimpanannya?
  3. Kuat untuk berapa users?

Pertanyaan ketiga hampir selalu salah pertanyaan. "Kuat untuk 40 orang"
tidak punya arti sampai disebut 40 orang yang bertanya SEBERAPA SERING.
40 orang yang masing-masing bertanya sekali sehari adalah beban yang
sepenuhnya berbeda dari 40 orang yang menekan tombol bersamaan pada
pukul 09.00. Yang kedua itulah yang sebenarnya ditanyakan, dan angkanya
adalah PERMINTAAN BERSAMAAN, bukan jumlah pegawai.
"""
from __future__ import annotations

import time

from ragcore import config

# Ukuran yang bisa dihitung dari angka, bukan diukur.
BYTE_PER_DIMENSI = 4                    # float32
HNSW_INDEX_RATIO = 0.45               # HNSW menambah ~40-50% di atas tabel


def measure_rate(example_page: list, extract) -> dict:
    """Ukur laju ekstraksi di mesin Anda sendiri.

    Jangan memakai angka orang lain. Selisih antar kartu grafis bisa lima
    kali lipat, dan selisih antara GPU dan CPU bisa dua puluh kali. Angka
    yang dipinjam akan membuat perkiraan yang meleset jauh, dan yang
    menanggung adalah janji yang sudah terlanjur diberikan.
    """
    mulai = time.perf_counter()
    for h in example_page:
        extract(h)
    total = time.perf_counter() - mulai

    page_per = total / max(len(example_page), 1)
    return {
        "contoh": len(example_page),
        "detik_per_halaman": round(page_per, 1),
        "halaman_per_jam": int(3600 / page_per) if page_per else 0,
    }


def indexing_time(page_total: int, page_per_seconds: float,
                       scan_ratio: float = 1.0) -> dict:
    """Perkiraan waktu mengindeks seluruh arsip.

    porsi_pindaian: bagian arsip yang butuh VLM. Halaman ber-lapisan teks
    diproses ratusan kali lebih cepat, jadi ia praktis tidak masuk hitungan.
    """
    vlm_page = page_total * scan_ratio
    seconds = vlm_page * page_per_seconds
    return {
        "halaman_vlm": int(vlm_page),
        "jam": round(seconds / 3600, 1),
        "hari_kerja_8jam": round(seconds / 3600 / 8, 1),
    }


def storage_needs(page_total: int, chunks_per_page: float = 2.0,
                          chars_per_chunk: int = 1000,
                          dim: int | None = None) -> dict:
    """Perkiraan besar storage indeks."""
    dim = dim or config.EMBEDDING_DIM
    chunks = page_total * chunks_per_page

    kb_vector = dim * BYTE_PER_DIMENSI / 1024
    kb_text = chars_per_chunk / 1024
    metadata_kb = 0.3
    per_chunk = kb_vector + kb_text + metadata_kb
    index_with = per_chunk * (1 + HNSW_INDEX_RATIO)

    return {
        "potongan": int(chunks),
        "kb_per_potongan": round(per_chunk, 1),
        "kb_per_potongan_dengan_indeks": round(index_with, 1),
        "total_mb": round(chunks * index_with / 1024, 1),
        "total_gb": round(chunks * index_with / 1024 / 1024, 2),
    }


def throughput(seconds_per_answer: float = 12.0, parallel_lanes: int = 1,
                 bersamaan: tuple[int, ...] = (5, 10, 20, 40)) -> list[dict]:
    """Waktu tunggu terburuk untuk sejumlah permintaan BERSAMAAN.

    jalur_paralel berasal dari OLLAMA_NUM_PARALLEL - dan menaikkannya hanya
    berarti bila memorinya cukup. Di kartu 6 GB yang sudah memuat model
    vision, jalurnya praktis satu.
    """
    result = []
    for n in bersamaan:
        seconds = (n / max(parallel_lanes, 1)) * seconds_per_answer
        result.append({
            "bersamaan": n,
            "tunggu_detik": round(seconds),
            "tunggu_menit": round(seconds / 60, 1),
        })
    return result


def _thousands(n) -> str:
    """Format ribuan gaya Indonesia: 8412 -> '8.412'."""
    return f"{int(n):,}".replace(",", ".")


def worksheet(page_total: int, page_per_seconds: float,
                 scan_ratio: float = 1.0,
                 seconds_per_answer: float = 12.0,
                 parallel_lanes: int = 1) -> None:
    """Cetak lembar kerja lengkap untuk satu organisasi."""
    print(f"\n  Arsip: {_thousands(page_total)} halaman, "
          f"{scan_ratio:.0%} di antaranya hasil pindaian")

    w = indexing_time(page_total, page_per_seconds, scan_ratio)
    print("\n  1. Waktu pengindeksan")
    print(f"     {_thousands(w['halaman_vlm'])} halaman lewat VLM "
          f"@ {page_per_seconds} detik")
    print(f"     -> {w['jam']} jam ({w['hari_kerja_8jam']} hari kerja)")
    print("     Sekali di awal. Pembaruan harian jauh lebih kecil.")

    s = storage_needs(page_total)
    print("\n  2. Penyimpanan")
    print(f"     {_thousands(s['potongan'])} potongan "
          f"@ {s['kb_per_potongan_dengan_indeks']} KB")
    print(f"     -> {s['total_gb']} GB (sudah termasuk indeks HNSW)")
    print("     Kecil. Yang besar adalah dokumen aslinya, bukan indeksnya.")

    print(f"\n  3. Daya tampung ({parallel_lanes} jalur paralel)")
    for d in throughput(seconds_per_answer, parallel_lanes):
        print(f"     {d['bersamaan']:>3} bersamaan -> tunggu {d['tunggu_menit']:>5.1f} menit")
    print("\n     Perhatikan: ini permintaan BERSAMAAN, bukan jumlah pegawai.")
    print("     Tanyakan balik ke atasan: berapa orang yang benar-benar")
    print("     bertanya pada saat yang sama? Angkanya hampir selalu jauh")
    print("     lebih kecil daripada jumlah pegawai - dan kalau tidak,")
    print("     yang dibutuhkan adalah antrean, bukan mesin yang lebih besar.")
