# Lembar kerja — perencanaan kapasitas (L13)

Isi dengan angka **arsip Anda sendiri**. Angka orang lain akan meleset jauh:
selisih antar kartu grafis bisa lima kali lipat.

## 1. Ukur dulu di mesin Anda

```bash
python -m rag_lab12.perintah.ekstrak dokumen_pindaian/SOP-01-Kepegawaian-PINDAI.pdf --ulang
```

Catat waktunya, bagi dengan jumlah halaman.

| | Nilai |
|---|---|
| Detik per halaman (VLM) | `____` |
| Kartu grafis / CPU | `____` |
| Waktu satu jawaban lengkap (detik) | `____` |

## 2. Arsip yang akan diindeks

| | Nilai |
|---|---|
| Total halaman | `____` |
| Porsi yang hasil pindaian | `____ %` |
| Perkiraan potongan per halaman | `____` |

## 3. Hitung

```bash
python -m rag_lab12.perintah.kapasitas --halaman ____ --detik ____ --porsi ____
```

| Pertanyaan atasan | Jawaban Anda |
|---|---|
| Berapa lama mengindeks seluruh arsip? | `____` jam |
| Berapa besar penyimpanannya? | `____` GB |
| Kuat untuk berapa pengguna? | lihat butir 4 |

## 4. Pertanyaan ketiga adalah pertanyaan yang salah

"Kuat untuk 40 orang" tidak punya arti sampai disebut 40 orang yang bertanya
**seberapa sering**. 40 orang yang masing-masing bertanya sekali sehari adalah
beban yang sepenuhnya berbeda dari 40 orang yang menekan tombol bersamaan
pada pukul 09.00.

| | Nilai |
|---|---|
| Jumlah pegawai | `____` |
| Yang benar-benar memakai sistem | `____` |
| Permintaan **bersamaan** pada jam sibuk | `____` |
| Waktu tunggu terburuk yang masih diterima | `____` menit |

Kalau waktu tunggu melebihi yang diterima, yang dibutuhkan sering **antrean**
dengan pemberitahuan — bukan mesin yang lebih besar.

## 5. Yang Anda sampaikan ke atasan

> Pengindeksan awal `____` jam, sekali di awal. Penyimpanan `____` GB. Pada
> `____` permintaan bersamaan, tunggu terburuk `____` menit. Di atas itu perlu
> `<antrean / GPU tambahan / pengindeksan di luar jam kerja>`.
