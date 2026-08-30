# Batas tanggung jawab

Isi bagian bertanda `<...>` sebelum sistem diserahkan.

## Sistem ini BOLEH dipakai untuk

- Mencari ketentuan di dokumen internal yang sudah diindeks
- Memeriksa kesesuaian data operasional terhadap ketentuan tersebut
- Menyiapkan bahan telaah yang akan dibaca manusia

## Sistem ini TIDAK BOLEH dipakai sebagai

- Dasar tunggal keputusan yang berakibat hukum atau kepegawaian
- Sumber informasi bagi pihak di luar organisasi
- Pengganti pembacaan dokumen aslinya untuk urusan berkonsekuensi

## Kalau jawabannya salah

Setiap jawaban menyertakan sitasi ke dokumen dan halaman. Pengguna
**bertanggung jawab memeriksa sitasi** sebelum menindaklanjuti hal yang
berkonsekuensi. Ini dinyatakan pada antarmuka, bukan hanya di dokumen ini.

Jawaban yang bersumber dari halaman hasil ekstraksi otomatis diberi
peringatan tersendiri. Angka di dalamnya belum diverifikasi manusia.

## Cakupan indeks per `<tanggal>`

```
Terindeks   : <jenis dokumen, rentang tahun, jumlah halaman>
Tidak masuk : <yang tidak diindeks>
Akibatnya   : pertanyaan di luar cakupan dijawab "tidak ditemukan" —
              itu BENAR, bukan kerusakan.
```

## Siapa merawat apa

| Urusan | Penanggung jawab | Cadangan |
|---|---|---|
| Indeks dan pengindeksan ulang | `<nama>` | `<nama>` |
| Basis data dan pencadangan | `<nama>` | `<nama>` |
| Perubahan prompt dan model | `<nama>`, dengan pengukuran ulang | `<nama>` |
| Penambahan dokumen baru | `<nama>` | `<nama>` |

## Ambang peringatan

Dijalankan sekali sehari, bukan real-time. Peringatan yang terlalu sering
dibaca orang akan berhenti dibaca.

| Peringatan | Ambang | Tindakan |
|---|---|---|
| Porsi penolakan melonjak | > 2x rata-rata sepekan | RUNBOOK: "semua dijawab tidak ditemukan" |
| Jawaban tanpa sitasi | > 0 | Selidiki segera — ini tidak boleh terjadi |
| Tidak ada pertanyaan sama sekali | 0 sehari penuh | Sistem mungkin tak terjangkau |
| Cakupan sitasi rata-rata turun | < 0,7 | Periksa mutu ekstraksi sumber baru |
