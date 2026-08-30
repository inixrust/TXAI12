-- =====================================================================
-- PT Nusantara Cipta Solusi — basis data operasional
-- Untuk kelas TX-AI12. Dijalankan sebagai pengguna NCS.
--
-- PENTING BAGI INSTRUKTUR
-- Isi tabel ini SENGAJA mengandung pelanggaran terhadap SOP yang ada di
-- korpus dokumen. Itulah gunanya: pertanyaan seperti "adakah pengadaan
-- yang disetujui pejabat tidak berwenang?" hanya bisa dijawab dengan
-- membaca aturannya dari DOKUMEN dan datanya dari BASIS DATA.
--
-- Peta pelanggaran ada di README.md — jangan dibagikan ke peserta
-- sebelum lab selesai.
--
-- Butuh Oracle Database Free 23ai (DROP ... IF EXISTS).
-- =====================================================================

-- Urutan penting: tabel anak dulu, karena mengacu ke karyawan.
DROP TABLE IF EXISTS sppd;
DROP TABLE IF EXISTS lembur;
DROP TABLE IF EXISTS cuti;
DROP TABLE IF EXISTS pengadaan;
DROP TABLE IF EXISTS karyawan;

-- ------------------------------------------------------------------ karyawan
CREATE TABLE karyawan (
  nip            VARCHAR2(10)  PRIMARY KEY,
  nama           VARCHAR2(60)  NOT NULL,
  golongan       VARCHAR2(20)  NOT NULL,   -- selaras SE-12: Direksi/Kepala Divisi/Manajer/Staf
  unit           VARCHAR2(40)  NOT NULL,
  tanggal_masuk  DATE          NOT NULL,
  status         VARCHAR2(20)  NOT NULL    -- tetap / kontrak / percobaan
);

-- CATATAN PENTING: `golongan` dan `jabatan_penyetuju` adalah DUA SUMBU YANG
-- BERBEDA, dan itu sengaja.
--
--   golongan          = jenjang kepegawaian (Direksi/Kepala Divisi/Manajer/Staf)
--   jabatan_penyetuju = PERAN dalam alur persetujuan menurut SOP-02 Pasal 2
--                       dan SE-12 Pasal 2 (Kepala Unit Kerja, Kepala Divisi,
--                       Direktur Keuangan, Direktur Utama)
--
-- Seorang Manajer bisa menjabat Kepala Unit Kerja. Yang TIDAK boleh terjadi
-- adalah jabatan setingkat Direksi diisi orang yang golongannya di bawah itu —
-- karena itu Direktur Keuangan diberi barisnya sendiri di bawah.
--
-- Peserta yang menyilangkan nama penyetuju ke golongan akan menemukan
-- perbedaan ini. Itu pertanyaan yang bagus, bukan cacat data; jawabannya
-- ada di komentar ini.
INSERT INTO karyawan VALUES ('NCS-0001','Chandra Halim','Direksi','Direksi',DATE '2018-03-01','tetap');
INSERT INTO karyawan VALUES ('NCS-0002','Ratna Kusuma','Direksi','Direksi',DATE '2018-09-01','tetap');
INSERT INTO karyawan VALUES ('NCS-0007','Bramantyo Wijaya','Kepala Divisi','Divisi SDM',DATE '2019-07-15','tetap');
INSERT INTO karyawan VALUES ('NCS-0012','Andini Prasetya','Manajer','Divisi SDM',DATE '2020-02-03','tetap');
INSERT INTO karyawan VALUES ('NCS-0023','Budi Santoso','Staf','Divisi TI',DATE '2023-09-04','tetap');
INSERT INTO karyawan VALUES ('NCS-0031','Sinta Rahmawati','Manajer','Divisi TI',DATE '2021-01-11','tetap');
INSERT INTO karyawan VALUES ('NCS-0044','Dewi Lestari','Staf','Divisi Keuangan',DATE '2024-06-17','tetap');
INSERT INTO karyawan VALUES ('NCS-0052','Eko Purnomo','Kepala Divisi','Divisi Keuangan',DATE '2017-11-06','tetap');
INSERT INTO karyawan VALUES ('NCS-0068','Fitri Handayani','Staf','Divisi Pengadaan',DATE '2025-03-10','tetap');
INSERT INTO karyawan VALUES ('NCS-0077','Gunawan Saputra','Manajer','Divisi Pengadaan',DATE '2022-08-22','tetap');
INSERT INTO karyawan VALUES ('NCS-0089','Hesti Wulandari','Staf','Divisi TI',DATE '2026-06-01','percobaan');
INSERT INTO karyawan VALUES ('NCS-0090','Irfan Maulana','Staf','Divisi Keuangan',DATE '2026-05-18','percobaan');
INSERT INTO karyawan VALUES ('NCS-0095','Joko Prabowo','Staf','Divisi Umum',DATE '2024-01-08','kontrak');

-- ------------------------------------------------------------------ cuti
-- Aturannya di SOP-01 Pasal 5 dan 6:
--   hak 12 hari kerja setahun · ajukan paling lambat H-7 hari kerja
--   cuti berturut-turut > 5 hari kerja wajib persetujuan Kepala Divisi
CREATE TABLE cuti (
  id                 NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nip                VARCHAR2(10)  REFERENCES karyawan(nip),
  tanggal_ajuan      DATE          NOT NULL,
  tanggal_mulai      DATE          NOT NULL,
  tanggal_selesai    DATE          NOT NULL,
  jumlah_hari        NUMBER(3)     NOT NULL,
  disetujui_oleh     VARCHAR2(60),
  jabatan_penyetuju  VARCHAR2(20),
  status             VARCHAR2(20)  NOT NULL
);

-- taat aturan
INSERT INTO cuti (nip,tanggal_ajuan,tanggal_mulai,tanggal_selesai,jumlah_hari,disetujui_oleh,jabatan_penyetuju,status)
VALUES ('NCS-0044',DATE '2026-05-04',DATE '2026-05-18',DATE '2026-05-20',3,'Eko Purnomo','Kepala Divisi','disetujui');
INSERT INTO cuti (nip,tanggal_ajuan,tanggal_mulai,tanggal_selesai,jumlah_hari,disetujui_oleh,jabatan_penyetuju,status)
VALUES ('NCS-0031',DATE '2026-06-01',DATE '2026-06-15',DATE '2026-06-17',3,'Sinta Rahmawati','Manajer','disetujui');
INSERT INTO cuti (nip,tanggal_ajuan,tanggal_mulai,tanggal_selesai,jumlah_hari,disetujui_oleh,jabatan_penyetuju,status)
VALUES ('NCS-0068',DATE '2026-06-22',DATE '2026-07-13',DATE '2026-07-20',6,'Eko Purnomo','Kepala Divisi','disetujui');

-- PELANGGARAN 1 — diajukan H-2, SOP mewajibkan H-7
INSERT INTO cuti (nip,tanggal_ajuan,tanggal_mulai,tanggal_selesai,jumlah_hari,disetujui_oleh,jabatan_penyetuju,status)
VALUES ('NCS-0023',DATE '2026-07-06',DATE '2026-07-08',DATE '2026-07-10',3,'Sinta Rahmawati','Manajer','disetujui');

-- PELANGGARAN 2 — 7 hari kerja, hanya disetujui Manajer; wajib Kepala Divisi
INSERT INTO cuti (nip,tanggal_ajuan,tanggal_mulai,tanggal_selesai,jumlah_hari,disetujui_oleh,jabatan_penyetuju,status)
VALUES ('NCS-0089',DATE '2026-07-01',DATE '2026-07-20',DATE '2026-07-28',7,'Sinta Rahmawati','Manajer','disetujui');

-- ------------------------------------------------------------------ lembur
-- Aturannya di SOP-01 Pasal 9:
--   > 3 jam sehari wajib persetujuan tambahan Kepala Divisi
--   maksimum 14 jam dalam satu minggu
CREATE TABLE lembur (
  id                 NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nip                VARCHAR2(10)  REFERENCES karyawan(nip),
  tanggal            DATE          NOT NULL,
  jam                NUMBER(4,1)   NOT NULL,
  disetujui_oleh     VARCHAR2(60),
  jabatan_penyetuju  VARCHAR2(20)
);

-- pekan 6–10 Juli 2026, Budi: 3+4+3+3+3 = 16 jam  -> PELANGGARAN 3 (batas 14 jam)
-- dan tanggal 7 Juli 4 jam hanya disetujui Manajer -> PELANGGARAN 4 (>3 jam wajib Kepala Divisi)
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0023',DATE '2026-07-06',3.0,'Sinta Rahmawati','Manajer');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0023',DATE '2026-07-07',4.0,'Sinta Rahmawati','Manajer');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0023',DATE '2026-07-08',3.0,'Sinta Rahmawati','Manajer');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0023',DATE '2026-07-09',3.0,'Sinta Rahmawati','Manajer');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0023',DATE '2026-07-10',3.0,'Sinta Rahmawati','Manajer');

-- taat aturan: 4 jam, disetujui Kepala Divisi; total pekan itu 10 jam
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0044',DATE '2026-07-06',4.0,'Eko Purnomo','Kepala Divisi');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0044',DATE '2026-07-08',3.0,'Eko Purnomo','Kepala Divisi');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0044',DATE '2026-07-09',3.0,'Eko Purnomo','Kepala Divisi');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0068',DATE '2026-07-07',2.0,'Gunawan Saputra','Manajer');
INSERT INTO lembur (nip,tanggal,jam,disetujui_oleh,jabatan_penyetuju) VALUES ('NCS-0095',DATE '2026-07-09',2.5,'Gunawan Saputra','Manajer');

-- ------------------------------------------------------------------ pengadaan
-- Aturannya di SOP-02 Pasal 2, 3, dan 5:
--   <= 10 jt              pembelian langsung     Kepala Unit Kerja
--   10 jt  – 100 jt       permintaan penawaran   Kepala Divisi      (min 3 penawaran)
--   100 jt – 500 jt       seleksi terbatas       Direktur Keuangan
--   > 500 jt              seleksi terbuka        Direktur Utama
--   uang muka maks 30% dan HANYA untuk pengadaan di atas Rp 100.000.000
--   pemecahan nilai untuk menghindari kewenangan lebih tinggi: dilarang
CREATE TABLE pengadaan (
  id                 NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nomor_po           VARCHAR2(24)  NOT NULL,
  tanggal            DATE          NOT NULL,
  unit               VARCHAR2(40)  NOT NULL,
  uraian             VARCHAR2(120) NOT NULL,
  nilai              NUMBER(14)    NOT NULL,
  metode             VARCHAR2(30)  NOT NULL,
  jumlah_penawaran   NUMBER(2),
  uang_muka_persen   NUMBER(3)     DEFAULT 0,
  disetujui_oleh     VARCHAR2(60),
  jabatan_penyetuju  VARCHAR2(24),
  -- Justifikasi tertulis bila SOP mensyaratkannya. NULL berarti TIDAK ADA
  -- yang tercatat -- dan itu FAKTA, bukan kolom yang kebetulan tak terisi.
  --
  -- Tanpa kolom ini, pelanggaran #6 (PO-0175, hanya 2 penawaran) mustahil
  -- diputuskan: SOP-02 Pasal 3 ayat (2) mengizinkan kurang dari 3 penawaran
  -- ASALKAN ada berita acara yang disetujui Direktur Keuangan. Agent yang
  -- jujur hanya bisa menjawab "tidak dapat dipastikan". Dengan kolom ini,
  -- ketiadaan justifikasi menjadi sesuatu yang bisa ditunjuk.
  keterangan         VARCHAR2(200)
);

-- taat aturan
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0134',DATE '2026-05-06','Divisi Umum','Alat tulis kantor triwulan II',7500000,'pembelian langsung',1,0,'Joko Prabowo','Kepala Unit Kerja',NULL);
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0141',DATE '2026-05-19','Divisi TI','Lisensi antivirus 200 lisensi',68000000,'permintaan penawaran',3,0,'Eko Purnomo','Kepala Divisi',NULL);
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
-- Penyetujunya Ratna Kusuma (Direksi), BUKAN Eko Purnomo (Kepala Divisi).
-- Rp 320 juta masuk rentang 100-500 juta, dan SOP-02 Pasal 2 menyerahkannya
-- ke Direktur Keuangan — jabatan setingkat Direksi.
VALUES ('PO-2026-0158',DATE '2026-06-09','Divisi TI','Server penyimpanan arsip digital',320000000,'seleksi terbatas',4,25,'Ratna Kusuma','Direktur Keuangan','Seleksi terbatas, 4 penawaran, berita acara BA-07/2026');
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0163',DATE '2026-06-23','Divisi Umum','Renovasi ruang rapat lantai 3',540000000,'seleksi terbuka',5,20,'Chandra Halim','Direktur Utama','Seleksi terbuka, diumumkan 14 hari');

-- PELANGGARAN 5 — Rp 85 jt disetujui Kepala Unit Kerja, kewenangan Kepala Divisi
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0170',DATE '2026-07-02','Divisi Pengadaan','Perangkat jaringan cabang Bandung',85000000,'permintaan penawaran',3,0,'Gunawan Saputra','Kepala Unit Kerja',NULL);

-- PELANGGARAN 6 — metode permintaan penawaran hanya 2 penawaran, minimum 3
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0175',DATE '2026-07-08','Divisi SDM','Pelatihan kepemimpinan 2 angkatan',45000000,'permintaan penawaran',2,0,'Bramantyo Wijaya','Kepala Divisi',NULL);

-- PELANGGARAN 7 — uang muka 30% pada pengadaan Rp 60 jt; hanya boleh di atas Rp 100 jt
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0181',DATE '2026-07-14','Divisi Keuangan','Jasa audit sistem informasi',60000000,'permintaan penawaran',3,30,'Eko Purnomo','Kepala Divisi',NULL);

-- PELANGGARAN 8 — pemecahan nilai. Dua PO hari sama, unit sama, barang sejenis,
-- masing-masing di bawah Rp 10 jt. Digabung Rp 19,4 jt -> kewenangan Kepala Divisi.
-- Ini kasus yang paling menarik: tidak ada satu baris pun yang salah sendirian.
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0188',DATE '2026-07-21','Divisi TI','Pengadaan laptop staf - tahap 1',9800000,'pembelian langsung',1,0,'Sinta Rahmawati','Kepala Unit Kerja','Kebutuhan mendesak divisi');
INSERT INTO pengadaan (nomor_po,tanggal,unit,uraian,nilai,metode,jumlah_penawaran,uang_muka_persen,disetujui_oleh,jabatan_penyetuju,keterangan)
VALUES ('PO-2026-0189',DATE '2026-07-21','Divisi TI','Pengadaan laptop staf - tahap 2',9600000,'pembelian langsung',1,0,'Sinta Rahmawati','Kepala Unit Kerja','Kebutuhan mendesak divisi');

-- ------------------------------------------------------------------ sppd
-- Aturannya di SE-12 Pasal 1 dan 5:
--   SPPD diajukan paling lambat H-3 hari kerja
--   laporan pertanggungjawaban paling lambat 5 hari kerja setelah kembali
CREATE TABLE sppd (
  id                 NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nomor_sppd         VARCHAR2(24)  NOT NULL,
  nip                VARCHAR2(10)  REFERENCES karyawan(nip),
  tujuan             VARCHAR2(60)  NOT NULL,
  jenis_tujuan       VARCHAR2(30)  NOT NULL,  -- dalam provinsi / luar provinsi / luar negeri
  tanggal_ajuan      DATE          NOT NULL,
  tanggal_berangkat  DATE          NOT NULL,
  tanggal_kembali    DATE          NOT NULL,
  tanggal_laporan    DATE,
  jabatan_penyetuju  VARCHAR2(24),
  -- Alasan perjalanan mendadak, bila ada. NULL berarti tidak ada yang
  -- tercatat. Pelanggaran #9 (SPPD-0251, diajukan H-1) bergantung pada ini:
  -- SE-12 Pasal 1 ayat (3) mengizinkan H-1 untuk perjalanan MENDADAK dengan
  -- persetujuan Kepala Divisi -- dan penyetujunya memang Kepala Divisi.
  -- Tanpa kolom ini, baris itu justru terlihat SAH.
  keterangan         VARCHAR2(200)
);

-- taat aturan
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0212','NCS-0031','Surabaya','luar provinsi',DATE '2026-06-08',DATE '2026-06-15',DATE '2026-06-17',DATE '2026-06-22','Kepala Divisi',NULL);
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0230','NCS-0044','Bogor','dalam provinsi',DATE '2026-06-29',DATE '2026-07-06',DATE '2026-07-07',DATE '2026-07-10','Kepala Unit Kerja',NULL);
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0245','NCS-0007','Singapura','luar negeri',DATE '2026-07-01',DATE '2026-07-13',DATE '2026-07-16',DATE '2026-07-21','Direktur Utama',NULL);

-- PELANGGARAN 9 — diajukan H-1, tidak ada keterangan mendadak
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0251','NCS-0023','Semarang','luar provinsi',DATE '2026-07-19',DATE '2026-07-20',DATE '2026-07-22',DATE '2026-07-27','Kepala Divisi',NULL);

-- PELANGGARAN 10 — laporan 14 hari setelah kembali, batasnya 5 hari kerja
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0258','NCS-0077','Medan','luar provinsi',DATE '2026-07-13',DATE '2026-07-20',DATE '2026-07-23',DATE '2026-08-06','Kepala Divisi',NULL);

-- PELANGGARAN 11 — luar negeri disetujui Kepala Divisi, wajib Direktur Utama
INSERT INTO sppd (nomor_sppd,nip,tujuan,jenis_tujuan,tanggal_ajuan,tanggal_berangkat,tanggal_kembali,tanggal_laporan,jabatan_penyetuju,keterangan)
VALUES ('SPPD-2026-0263','NCS-0031','Kuala Lumpur','luar negeri',DATE '2026-07-27',DATE '2026-08-05',DATE '2026-08-07',NULL,'Kepala Divisi',NULL);

COMMIT;

-- ------------------------------------------------------------------ periksa
SELECT 'karyawan'  AS tabel, COUNT(*) AS baris FROM karyawan
UNION ALL SELECT 'cuti',      COUNT(*) FROM cuti
UNION ALL SELECT 'lembur',    COUNT(*) FROM lembur
UNION ALL SELECT 'pengadaan', COUNT(*) FROM pengadaan
UNION ALL SELECT 'sppd',      COUNT(*) FROM sppd;
