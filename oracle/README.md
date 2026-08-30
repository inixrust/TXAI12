# Basis Data Oracle untuk TX-AI12

Berkas ini untuk **instruktur**. Peta pelanggaran di bawah adalah kunci jawaban
lab — jangan dibagikan ke peserta sebelum lab L9 selesai.

## Menjalankan

```bash
# 1. Hidupkan Oracle Database Free (memakai compose yang ada di lab)
docker compose -f ../compose-oracle.yaml up -d

# Penyiapan pertama makan 5-10 menit. Tunggu sampai muncul:
docker logs -f oracle-txai12 | grep "DATABASE IS READY"
```

```bash
# 2. Buat pemilik data
sql system/Rahasia_Lab_2026@localhost:1521/FREEPDB1
```
```sql
CREATE USER ncs IDENTIFIED BY "Rahasia_Lab_2026"
  DEFAULT TABLESPACE users QUOTA UNLIMITED ON users;

-- CREATE SEQUENCE WAJIB ADA. Empat dari lima tabel memakai
-- GENERATED ALWAYS AS IDENTITY, dan Oracle membuat sequence secara
-- diam-diam untuk kolom itu. Tanpa hak ini, `karyawan` terbentuk normal
-- lalu keempat tabel sisanya gagal dengan ORA-01031: insufficient
-- privileges — galat yang tidak menyebut sequence sama sekali, dan
-- membuat orang mengira masalahnya di CREATE TABLE.
GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE SEQUENCE TO ncs;
EXIT
```

```bash
# 3. Isi datanya
sql ncs/"Rahasia_Lab_2026"@localhost:1521/FREEPDB1 @01-schema-and-data.sql

# 4. Pasang pembatas (sebagai SYSTEM)
sql system/Rahasia_Lab_2026@localhost:1521/FREEPDB1 @02-restrictions.sql

# 5. Buktikan pembatasnya bekerja
sql rag_baca/"Rahasia_Lab_2026"@localhost:1521/FREEPDB1
```
```sql
SELECT COUNT(*) FROM ncs.v_pengadaan;   -- 9 baris
DELETE FROM ncs.pengadaan;              -- ORA-00942
```

## Server MCP

**Sambungan tersimpan itu WAJIB, bukan kemudahan.** Tool `connect` pada server
MCP hanya menerima NAMA sambungan — ia tidak bisa diberi user/sandi. Tanpa
sambungan tersimpan, agent punya tool tetapi tidak punya basis data.

Dua cara, dan yang kedua tidak butuh terminal sama sekali:

```bash
# a. dari terminal sungguhan
sql /nolog
SQL> conn -save agentlab -savepwd rag_baca/Rahasia_Lab_2026@localhost:1521/FREEPDB1
SQL> exit

# b. lewat server MCP itu sendiri — tanpa TTY, dan inilah yang dipakai lab
python -m ragcore.commands.mcp --simpan-sambungan
```

Cara (b) memakai tool `sqlcl_run` pada server MCP untuk menjalankan
`conn -save`. Karena server MCP berkomunikasi lewat stdio berpipa, ia tidak
pernah menyentuh konsol — jadi satu-satunya langkah yang tadinya menuntut
terminal kini bisa dijalankan dari mana saja.

Lalu jalankan servernya:

```bash
sql -mcp
```

### Sudah diuji: 9 tool yang disediakan

```
annotation_generate   connect        connections_list   disconnect
request_status        schema_information                skills_sync
sql_run               sqlcl_run
```

Yang dipakai agent untuk bertanya adalah **`sql_run`**. Perhatikan namanya
BUKAN `tanya_basis_data` — nama tool MCP ditentukan Oracle dan berubah
antarversi. Itu sebabnya `evaluation/hybrid.py` mencocokkan nama secara
longgar; pencocokan persis akan rusak diam-diam pada pembaruan SQLcl
berikutnya, berupa skor nol yang terlihat seperti kegagalan model.

### Catatan TTY — penting bila menjalankan dari skrip atau CI

Skrip peluncur SQLcl membangun konsol interaktif lebih dulu, dan gagal tanpa
TTY:

```
java.io.IOException: Incorrect function
```

Mode `-mcp` sendiri TIDAK butuh konsol — ia berkomunikasi lewat stdio berpipa.
Untuk lingkungan tanpa TTY, panggil kelas utamanya langsung dengan menyetel
`SQLCL_HOME`; lab akan menyusun perintahnya sendiri (lihat
`agent/hybrid.py:mcp_command`). Diuji pada **SQLcl 26.2.1** dengan Java 17.

Yang tetap TIDAK bisa tanpa TTY: `conn -save`. Jadi sambungan tersimpan harus
dibuat sekali dari terminal biasa.

### SQLcl tidak perlu diunduh terpisah — sudah ada di dalam container

Image Oracle Database Free 26ai membawa SQLcl 26.2 lengkap di
`$ORACLE_HOME/sqlcl`. Tetapi ia TIDAK bisa dijalankan di dalam container:
JDK bawaan image itu Java 11, sedangkan `-mcp` menuntut Java 17.

```
Error: SQLcl -mcp requires Java 17 and above to run.
       Found Java version 11.
```

Jadi salin keluar, lalu jalankan dengan Java 17 milik host:

```bash
docker cp oracle-txai12:/opt/oracle/product/26ai/dbhomeFree/sqlcl C:/Users/<anda>/sqlcl
```

lalu setel `SQLCL_HOME` ke folder itu (lihat `.env.example`). Jalur SQLCL_HOME
memanggil kelas utama SQLcl langsung, jadi masalah TTY di atas ikut hilang.

Menjalankan `docker exec -i ... sql -mcp` juga tidak menolong: stdio berpipa
memang sampai, tetapi Java di dalamnya tetap yang salah versi.

Yang TIDAK ikut tersalin adalah sambungan tersimpan — itu ada di profil
pengguna, bukan di folder SQLcl. Buat sekali dengan:

```bash
python -m ragcore.commands.mcp --simpan-sambungan
```

## Rancangan: kenapa datanya begini

Setiap tabel bersambung dengan satu bagian SOP di korpus dokumen. Bukan
kebetulan — itulah yang membuat pertanyaan hibrida punya jawaban.

| Tabel | Aturannya ada di | Yang diuji |
|---|---|---|
| `cuti` | SOP-01 Pasal 5, 6 | batas waktu pengajuan, jenjang persetujuan |
| `lembur` | SOP-01 Pasal 9 | batas jam harian dan mingguan |
| `pengadaan` | SOP-02 Pasal 2, 3, 5 | tabel kewenangan, jumlah penawaran, uang muka |
| `sppd` | SE-12 Pasal 1, 2, 5 | batas pengajuan, kewenangan, batas laporan |

Perhatikan bahwa **keempat tabel aturannya berada di halaman pindaian** —
`cuti` dan `lembur` sama-sama diatur SOP-01, jadi tiga dokumen pindaian
menutupi empat tabel. Kalau ekstraksi Hari 1 gagal, lab hibrida Hari 3 ikut gagal —
dan itu memang disengaja. Peserta perlu merasakan bahwa mutu ekstraksi
bukan urusan tersendiri.

## Peta pelanggaran — kunci jawaban (12 pelanggaran)

| # | Letak | Pelanggaran | Aturan yang dilanggar |
|---|---|---|---|
| 1 | `cuti` Budi Santoso | Diajukan H-2 | SOP-01 Pasal 6 ayat (1): H-7 |
| 2 | `cuti` Hesti Wulandari | 7 hari disetujui Manajer | SOP-01 Pasal 5 ayat (3): >5 hari wajib Kepala Divisi |
| 3 | `lembur` Budi Santoso | 16 jam sepekan | SOP-01 Pasal 9 ayat (5): maks 14 jam |
| 4 | `lembur` Budi, 7 Juli | 4 jam disetujui Manajer | SOP-01 Pasal 9 ayat (3): >3 jam wajib Kepala Divisi |
| 5 | `pengadaan` PO-0170 | Rp 85 jt disetujui Kepala Unit | SOP-02 Pasal 2: kewenangan Kepala Divisi |
| 6 | `pengadaan` PO-0175 | 2 penawaran | SOP-02 Pasal 3: minimum 3 |
| 7 | `pengadaan` PO-0181 | Uang muka 30% pada Rp 60 jt | SOP-02 Pasal 5: hanya di atas Rp 100 jt |
| 8 | `pengadaan` PO-0188 + 0189 | Pemecahan nilai | SOP-02 Pasal 2 ayat (2) |
| 9 | `sppd` SPPD-0251 | Diajukan H-1 | SE-12 Pasal 1 ayat (2): H-3 |
| 10 | `sppd` SPPD-0258 | Laporan telat 14 hari | SE-12 Pasal 5 ayat (1): 5 hari kerja |
| 11 | `sppd` SPPD-0263 | Luar negeri disetujui Kepala Divisi | SE-12 Pasal 2: wajib Direktur Utama |
| 12 | `cuti` Hesti Wulandari | Cuti tahunan padahal masa kerja < 12 bulan | SOP-01 Pasal 5 ayat (1) |

### Pelanggaran 12 — yang paling mudah terlewat instruktur

Hesti Wulandari (NCS-0089) masuk **1 Juni 2026**, berstatus `percobaan`, dan
mengambil cuti tahunan **20 Juli 2026**. SOP-01 Pasal 5 ayat (1) memberi hak
cuti tahunan hanya kepada yang telah bekerja **12 bulan berturut-turut**. Ia
baru tujuh minggu.

Barisnya sama dengan pelanggaran 2, jadi satu baris memuat DUA pelanggaran
sekaligus: haknya belum ada, dan persetujuannya pun kurang. Peserta yang
menemukan salah satunya sudah benar; yang menemukan keduanya lebih teliti
daripada kunci jawaban versi pertama.

Menemukannya menuntut `v_karyawan` dan `v_cuti` sekaligus — dan itu justru
jenis pertanyaan yang paling layak dilatih.

### Kenapa `jabatan_penyetuju` kadang tak sejalan dengan `golongan`

Keduanya **sumbu yang berbeda**, dan itu disengaja:

| kolom | artinya |
|---|---|
| `karyawan.golongan` | jenjang kepegawaian: Direksi / Kepala Divisi / Manajer / Staf |
| `jabatan_penyetuju` | PERAN dalam alur persetujuan menurut SOP-02 Pasal 2 dan SE-12 Pasal 2 |

Seorang Manajer boleh menjabat Kepala Unit Kerja — itu sah. Yang tidak sah
adalah jabatan setingkat Direksi diisi orang di bawah jenjang itu; karena
itu **Ratna Kusuma (NCS-0002, Direksi)** ada di tabel sebagai pemegang
Direktur Keuangan, dan PO-0158 disetujui olehnya.

Peserta yang menyilangkan nama penyetuju ke golongan akan menanyakan ini.
Pertanyaannya bagus, dan jawabannya ada di tabel di atas — bukan temuan
pelanggaran.

### Kolom `keterangan` — dan kenapa ia menentukan

`pengadaan` dan `sppd` punya kolom `keterangan`: justifikasi tertulis bila
SOP mensyaratkannya. **NULL berarti tidak ada yang tercatat**, dan itu fakta
yang bisa disimpulkan — bukan kolom yang kebetulan kosong.

Tanpa kolom ini, dua pelanggaran mustahil diputuskan dan agent yang JUJUR
hanya bisa menjawab "tidak dapat dipastikan":

| # | Pengecualian yang membuatnya ambigu | Kini terbaca sebagai |
|---|---|---|
| 6 | SOP-02 Pasal 3 (2): < 3 penawaran sah bila ada berita acara | PO-0175 → `keterangan` NULL |
| 9 | SE-12 Pasal 1 (3): H-1 sah bila perjalanan mendadak | SPPD-0251 → `keterangan` NULL |

Perhatikan pelanggaran 9: penyetujunya memang Kepala Divisi, persis seperti
yang diminta pengecualian. Tanpa kolom `keterangan`, baris itu justru
terlihat **sah**.

Sebagai pembanding, PO-0158 memuat `'Seleksi terbatas, 4 penawaran, berita
acara BA-07/2026'` — contoh justifikasi yang ada, supaya peserta melihat
kedua sisinya.

### Yang paling berharga diajarkan: pelanggaran nomor 8

Sepuluh pelanggaran pertama bisa ditemukan dengan satu query per aturan.
Pelanggaran kedelapan tidak: **tidak ada satu baris pun yang salah kalau
dilihat sendirian**. PO-0188 senilai Rp 9,8 juta sah. PO-0189 senilai
Rp 9,6 juta juga sah. Yang melanggar adalah hubungan di antara keduanya.

Sebagian besar agent akan melewatkan ini, dan itu bukan kegagalan lab —
itu bahan diskusinya. Pertanyaan yang layak diajukan ke kelas:

> Apa yang harus ditambahkan supaya sistem bisa menemukan pola semacam ini —
> instruksi yang lebih baik, alat yang lebih spesifik, atau justru manusia
> yang memeriksa?

Jawaban jujurnya sering yang ketiga. Itu pelajaran yang lebih berguna
daripada agent yang kebetulan berhasil.

## Menghentikan dan membersihkan

```bash
docker compose -f ../compose-oracle.yaml stop
docker compose -f ../compose-oracle.yaml start   # data tetap, penyiapan tidak diulang
docker compose -f ../compose-oracle.yaml down -v  # hapus total, termasuk volume
```

## Sudah diuji pada Oracle sungguhan

Dijalankan pada **Oracle Database Free 26ai** (image `database/free:latest`),
dan kedua berkas kini berjalan tanpa galat. Yang ditemukan saat pengujian:

| Temuan | Keadaan |
|---|---|
| `CREATE SEQUENCE` tidak diberikan → 4 dari 5 tabel gagal | diperbaiki di atas |
| `CREATE PROFILE` / `CREATE AUDIT POLICY` gagal saat dijalankan ulang | diperbaiki, kini idempoten |
| `IF EXISTS` tidak didukung untuk DROP PROFILE / DROP AUDIT POLICY | ORA-11600; dipakai pemeriksaan katalog |
| `ALTER SESSION SET CONTAINER` dari dalam PDB | **berhasil** — sempat diduga gagal, ternyata tidak |
| `DROP TABLE IF EXISTS` | didukung |

Peragaan empat lapis pembatas juga sudah dibuktikan berjalan — lihat langkah 5.
Perhatikan image resminya kini **26ai**, bukan 23ai seperti tertulis di silabus.
