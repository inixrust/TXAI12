-- =====================================================================
-- Lapisan 6 lanjutan: SANDI PER-USER DI DATABASE (bukan hardcode).
--
-- Sebelum ini, semua user login dengan SATU sandi yang di-hardcode sebagai
-- hash SHA-256 di domain/users.py. Artinya: (a) sandi ada di dalam kode/ git,
-- (b) SHA-256 polos tanpa salt - cepat di-brute-force, dan (c) identitas
-- praktis hanya "pilih nama dari dropdown" karena semua orang tahu sandinya.
-- Itu melemahkan seluruh fondasi "identitas datang dari login, bukan pertanyaan".
--
-- Perbaikannya: hash argon2id PER-USER di tabel ncs.pengguna_auth, dibaca lewat
-- akun HAK-MINIMAL rag_auth yang TAK BISA membaca apa pun selain hash + identitas.
--
-- BATAS KEPERCAYAAN YANG PENTING:
--   - rag_auth  : SATU-SATUNYA akun yang boleh membaca ncs.pengguna_auth.
--   - rag_baca / rag_app / rag_operator (akun QUERY dokumen/tabel) TIDAK diberi
--     akses apa pun ke pengguna_auth. Kredensial query yang bocor TAK boleh
--     bisa membaca hash sandi siapa pun.
--   - rag_auth juga TAK diberi akses ke tabel sensitif (cuti/lembur/pengadaan/
--     sppd) maupun view-nya. Ia hanya baca pengguna_auth + karyawan (identitas).
--
-- Jalankan sebagai SYSTEM SETELAH 01-04. Idempoten.
-- =====================================================================

ALTER SESSION SET CONTAINER = FREEPDB1;

-- Tabel hash sandi. FK ke karyawan: sandi hanya boleh ada untuk pegawai yang
-- BENAR-BENAR terdaftar - tak ada akun hantu. hash_sandi menyimpan string PHC
-- lengkap argon2id ($argon2id$v=19$m=...$...$...), termasuk salt & parameter,
-- jadi tak perlu kolom salt terpisah.
DECLARE
  v_ada NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_ada
    FROM dba_tables WHERE owner = 'NCS' AND table_name = 'PENGGUNA_AUTH';
  IF v_ada = 0 THEN
    EXECUTE IMMEDIATE q'[
      CREATE TABLE ncs.pengguna_auth (
        nip         VARCHAR2(10)  PRIMARY KEY
                    REFERENCES ncs.karyawan(nip),
        hash_sandi  VARCHAR2(255) NOT NULL,
        algo        VARCHAR2(20)  DEFAULT 'argon2id' NOT NULL,
        diperbarui  TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL
      )]';
  END IF;
END;
/

-- Akun autentikasi hak-minimal (idempoten: abaikan bila sudah ada).
DECLARE
  v_ada NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_ada FROM dba_users WHERE username = 'RAG_AUTH';
  IF v_ada = 0 THEN
    EXECUTE IMMEDIATE 'CREATE USER rag_auth IDENTIFIED BY "Rahasia_Lab_2026"';
  END IF;
END;
/

GRANT CREATE SESSION TO rag_auth;

-- Dua grant, dan HANYA dua:
--   pengguna_auth - untuk mengambil hash sandi saat login.
--   karyawan      - untuk identitas (nama, unit) yang ditampilkan setelah login.
-- Tak ada grant ke tabel/ view sensitif. rag_auth tak bisa 'bertanya' apa pun.
GRANT SELECT ON ncs.pengguna_auth TO rag_auth;
GRANT SELECT ON ncs.karyawan      TO rag_auth;

-- Catatan produksi (di luar cakupan skrip lab): profil sumber daya untuk
-- rag_auth, dan sandinya di secret manager (OpenBao) - bukan konstanta di sini.
-- Hash sandi diisi oleh: python -m ragcore.commands.auth --seed
