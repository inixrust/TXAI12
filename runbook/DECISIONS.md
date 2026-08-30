# Keputusan dan alasannya

Yang perlu dicatat bukan APA yang dipilih — itu terbaca dari kode — melainkan
KENAPA, dan apa yang sudah dicoba dan gagal. Tanpa ini, orang berikutnya akan
mengulangi percobaan yang sama.

## bge-m3 sebagai model embedding

Bukan `nomic-embed-text`. Nomic dilatih terutama untuk bahasa Inggris dan
gagal secara **senyap** pada bahasa Indonesia — skornya tetap keluar dan
terlihat wajar. Diuji pada set uji internal: recall parafrasa turun jauh.

Mengganti model berarti membangun ulang **seluruh** indeks.

## qwen3-vl:4b sebagai model vision

Bukan model vision yang lebih besar. Bobotnya 3,3 GB, menyisakan sekitar
2,7 GB untuk token visual pada kartu 6 GB. Model yang lebih besar memaksa
turun ke CPU, dan ekstraksi yang tadinya 9 detik per halaman menjadi menit.

## Render 150 DPI untuk VLM, bukan 200

DPI menentukan jumlah token visual, dan token visual menentukan pemakaian
VRAM. 150 adalah titik aman untuk 6 GB. Berkas pindaiannya sendiri dibuat
pada 200 DPI — dua angka yang berbeda, dan sering tertukar saat dibahas.

## PostgreSQL + pgvector, bukan Chroma

Alasan yang menentukan bukan kecepatan, melainkan **penegakan**. Pembatasan
akses berupa `if` di aplikasi hanya berlaku pada jalur yang ingat memanggilnya.
Row-Level Security berlaku pada setiap kueri — termasuk kueri yang lupa
menyaring, termasuk psql milik orang lain.

Alasan berikutnya: pencadangan, replikasi, dan pemantauan sudah ada di
organisasi. Satu komponen yang tidak perlu dirawat sendiri.

## Menandai dokumen dicabut, bukan menghapusnya

"Kenapa sistem dulu menjawab begini?" adalah pertanyaan yang pasti datang, dan
hanya bisa dijawab kalau datanya masih ada. Penyaring status sudah menahannya
dari hasil pencarian, jadi tidak ada risiko ia terjawab lagi.

## Peninjauan manusia ditentukan aturan, bukan model

Kalau model yang memutuskan kapan ia perlu diperiksa, jawaban yang paling
percaya diri justru yang paling jarang diperiksa — dan itu kebalikan dari
yang dibutuhkan. Aturannya deterministik: cakupan sitasi di bawah ambang,
atau sumbernya hasil VLM yang belum diverifikasi.

## Lapis 2 pemeriksaan mutu hanya membandingkan angka

VLM merapikan tata letak, OCR mengikuti urutan piksel — susunan katanya pasti
berbeda. Membandingkan seluruh teks menghasilkan ketidaksepakatan palsu di
mana-mana, dan sinyal yang sesungguhnya tenggelam. Angka tidak begitu, dan di
dokumen SOP justru angka yang paling berkonsekuensi bila salah dibaca.

## `<keputusan Anda sendiri>`

`<apa yang dicoba, apa yang gagal, kenapa yang ini dipilih>`
