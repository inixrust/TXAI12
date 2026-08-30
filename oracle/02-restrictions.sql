-- =====================================================================
-- Empat lapisan pembatas untuk akses agent ke Oracle
-- Dijalankan sebagai SYSTEM di dalam PDB (FREEPDB1), bukan sebagai NCS.
--
-- Gagasan pokoknya: JANGAN mengandalkan prompt untuk menahan agent.
-- Prompt adalah permintaan; hak akses basis data adalah penegakan.
-- Kalau satu-satunya yang menghalangi DELETE adalah kalimat "jangan
-- menghapus data" di dalam prompt, maka tidak ada yang menghalangi.
-- =====================================================================

ALTER SESSION SET CONTAINER = FREEPDB1;

-- ------------------------------------------------------ Lapisan 1: akun terpisah
-- Agent TIDAK memakai akun pemilik data. Ia punya akunnya sendiri yang
-- sejak lahir tidak pernah diberi hak menulis.

DROP USER IF EXISTS rag_baca CASCADE;

CREATE USER rag_baca IDENTIFIED BY "Rahasia_Lab_2026";
GRANT CREATE SESSION TO rag_baca;

-- Tidak ada satu pun GRANT INSERT / UPDATE / DELETE / CREATE di bawah ini.
-- Bukan karena lupa — memang tidak boleh ada.


-- ------------------------------------------------------ Lapisan 2: tampilan penyaring
-- Agent tidak melihat tabel, ia melihat VIEW. Kolom sensitif tidak
-- disertakan sama sekali, jadi tidak ada cara memintanya.

CREATE OR REPLACE VIEW ncs.v_karyawan AS
SELECT nip, nama, golongan, unit, status
FROM   ncs.karyawan;
-- perhatikan: tanggal_masuk tidak ikut. Kalau kelak ada kolom gaji,
-- tempatnya adalah di luar view ini.

CREATE OR REPLACE VIEW ncs.v_cuti AS
SELECT c.id, k.nama, k.unit, c.tanggal_ajuan, c.tanggal_mulai,
       c.tanggal_selesai, c.jumlah_hari, c.jabatan_penyetuju, c.status
FROM   ncs.cuti c JOIN ncs.karyawan k ON k.nip = c.nip;

CREATE OR REPLACE VIEW ncs.v_lembur AS
SELECT l.id, k.nama, k.unit, l.tanggal, l.jam, l.jabatan_penyetuju
FROM   ncs.lembur l JOIN ncs.karyawan k ON k.nip = l.nip;

CREATE OR REPLACE VIEW ncs.v_pengadaan AS
SELECT nomor_po, tanggal, unit, uraian, nilai, metode,
       jumlah_penawaran, uang_muka_persen, jabatan_penyetuju,
       -- keterangan IKUT. Tanpa kolom ini agent tidak bisa membedakan
       -- "kurang dari 3 penawaran TANPA berita acara" (melanggar) dari
       -- "kurang dari 3 penawaran DENGAN berita acara" (sah menurut
       -- SOP-02 Pasal 3 ayat 2). Menyembunyikannya membuat agent yang
       -- jujur hanya bisa menjawab "tidak dapat dipastikan".
       keterangan
FROM   ncs.pengadaan;

CREATE OR REPLACE VIEW ncs.v_sppd AS
SELECT s.nomor_sppd, k.nama, k.golongan, s.tujuan, s.jenis_tujuan,
       s.tanggal_ajuan, s.tanggal_berangkat, s.tanggal_kembali,
       s.tanggal_laporan, s.jabatan_penyetuju,
       -- Sama alasannya: SE-12 Pasal 1 ayat (3) mengizinkan H-1 untuk
       -- perjalanan MENDADAK. Tanpa kolom ini, SPPD yang diajukan H-1
       -- justru terlihat sah -- pengecualiannya tak terbantahkan.
       s.keterangan
FROM   ncs.sppd s JOIN ncs.karyawan k ON k.nip = s.nip;

GRANT SELECT ON ncs.v_karyawan  TO rag_baca;
GRANT SELECT ON ncs.v_cuti      TO rag_baca;
GRANT SELECT ON ncs.v_lembur    TO rag_baca;
GRANT SELECT ON ncs.v_pengadaan TO rag_baca;
GRANT SELECT ON ncs.v_sppd      TO rag_baca;


-- ------------------------------------------------------ Lapisan 3: kuota sumber daya
-- Menahan kueri yang tak sengaja memindai seluruh tabel dan
-- menghabiskan CPU basis data produksi.

-- Idempoten. IF EXISTS TIDAK didukung untuk DROP PROFILE — diuji pada
-- Oracle 26ai dan ditolak dengan ORA-11600. Jadi katalognya diperiksa dulu.
-- Menelan semua galat dengan "WHEN OTHERS THEN NULL" akan menyembunyikan
-- kesalahan lain juga; memeriksa katalog hanya melewati yang memang tidak ada.
DECLARE
  jumlah NUMBER;
BEGIN
  SELECT COUNT(*) INTO jumlah FROM dba_profiles WHERE profile = 'RAG_PROFIL';
  IF jumlah > 0 THEN
    EXECUTE IMMEDIATE 'DROP PROFILE rag_profil CASCADE';
  END IF;
END;
/

-- CONNECT_TIME PUNYA AKIBAT YANG TIDAK TERDUGA, DAN LAYAK DIBAHAS DI KELAS.
--
-- Enam puluh menit terdengar longgar. Tetapi agent hibrida membuka SATU sesi
-- basis data di awal dan memakainya sampai selesai, dan evaluasi penuh dengan
-- --ulang 2 berjalan lebih dari satu jam. Di menit ke-60 Oracle memutus sesi
-- itu, persis sebagaimana diperintahkan di sini.
--
-- Yang terjadi berikutnya bukan galat. Setiap sql_run TETAP BERHASIL, hanya
-- isinya berubah menjadi teks "Connection not established". Agent membacanya
-- lalu menjawab dengan sopan: "Koneksi ke basis data terputus, informasi
-- tidak dapat diperiksa." Jawaban yang jujur, dinilai SALAH oleh evaluasi.
--
-- Terbukti di lab ini: seluruh kasus `aritmetika` mendapat 0% pada empat
-- jalan berturut-turut, dan terbaca persis seperti "model tidak bisa
-- menghitung selisih tanggal". Perbaikan yang benar BUKAN melonggarkan batas
-- ini - batasnya memang seharusnya ada - melainkan membuat klien menyambung
-- ulang saat sesinya diputus. Lihat agen/hibrida.bungkus_sambung_ulang().
--
-- Pelajarannya berlaku di luar lab: pembatas keamanan yang benar tetap bisa
-- merusak sistem lain, dan kerusakannya jarang muncul sebagai galat.
CREATE PROFILE rag_profil LIMIT
  CPU_PER_CALL            3000    -- 30 detik CPU per pernyataan
  LOGICAL_READS_PER_CALL  100000
  CONNECT_TIME            60      -- menit; lihat catatan di atas
  SESSIONS_PER_USER       2;

ALTER USER rag_baca PROFILE rag_profil;


-- ------------------------------------------------------ Lapisan 4: jejak audit
-- Bukan untuk mencegah, melainkan untuk menjawab pertanyaan
-- "apa saja yang pernah ditanyakan sistem itu ke basis data kita?"
-- Pertanyaan ini pasti datang dari tim keamanan, cepat atau lambat.

-- Idempoten juga, dan urutannya penting: kebijakan yang sedang AKTIF tidak
-- bisa langsung dibuang — harus di-NOAUDIT lebih dulu.
DECLARE
  jumlah NUMBER;
BEGIN
  SELECT COUNT(*) INTO jumlah
  FROM   audit_unified_enabled_policies WHERE policy_name = 'RAG_JEJAK';
  IF jumlah > 0 THEN
    EXECUTE IMMEDIATE 'NOAUDIT POLICY rag_jejak';
  END IF;

  SELECT COUNT(*) INTO jumlah
  FROM   audit_unified_policies WHERE policy_name = 'RAG_JEJAK';
  IF jumlah > 0 THEN
    EXECUTE IMMEDIATE 'DROP AUDIT POLICY rag_jejak';
  END IF;
END;
/

CREATE AUDIT POLICY rag_jejak
  ACTIONS SELECT ON ncs.v_karyawan,
          SELECT ON ncs.v_cuti,
          SELECT ON ncs.v_lembur,
          SELECT ON ncs.v_pengadaan,
          SELECT ON ncs.v_sppd;

AUDIT POLICY rag_jejak BY rag_baca;


-- ------------------------------------------------------ pembuktian
-- Jalankan sebagai rag_baca, lalu tunjukkan hasilnya di kelas.
-- Peragaan ini yang menutup perdebatan keamanan, bukan penjelasan.
--
--   sql rag_baca/"Rahasia_Lab_2026"@localhost:1521/FREEPDB1
--
--   SELECT COUNT(*) FROM ncs.v_pengadaan;     -- 9 baris, berhasil
--   DELETE FROM ncs.pengadaan;                -- ORA-00942: table or view does not exist
--   SELECT * FROM ncs.karyawan;               -- ORA-00942: tabelnya tak terlihat sama sekali
--
-- Perhatikan galatnya: bukan "tidak punya izin", melainkan
-- "tidak ada". Bagi agent, tabel itu tidak pernah ada.

SELECT 'siap' AS status FROM dual;
