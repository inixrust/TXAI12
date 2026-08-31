-- =====================================================================
-- Lapisan 6: PEMISAHAN AKUN query vs operator (penutupan penuh F-02).
--
-- Pentest menemukan residu F-02: pin sesi (03-row-scope.sql) menahan eskalasi
-- set_operator dari jalur APLIKASI, tetapi kredensial rag_baca yang menyambung
-- LANGSUNG pada sesi segar (pinned masih kosong) masih bisa memanggil
-- set_operator dan 'lihat semua'. Menutupnya sepenuhnya menuntut pemisahan hak
-- yang tak bisa dielakkan siapa pun yang memegang kredensial query.
--
-- DUA AKUN, HAK BERTINGKAT:
--   rag_baca     - akun PRODUKSI hak-minimal. Hanya boleh set_identity
--                  (penyaring per-unit). set_operator MENOLAKNYA di dalam
--                  prosedur (lihat 03-row-scope.sql: cek SESSION_USER). Jadi
--                  walau kredensialnya bocor, ia tak bisa mengeskalasi scope.
--   rag_operator - akun OPERATOR tepercaya (CLI, evaluasi, pemeliharaan).
--                  Superset: boleh set_identity DAN set_operator ('lihat
--                  semua'). Dipakai HANYA oleh jalur non-produksi.
--
-- Kenapa pemisahan di DALAM prosedur, bukan lewat GRANT paket: EXECUTE paket
-- bersifat all-or-nothing - memberi EXECUTE atas rag_scope memberi akses ke
-- set_identity DAN set_operator sekaligus. Karena itu set_operator sendiri yang
-- memeriksa SESSION_USER (lihat 03), dan kedua akun tetap ber-EXECUTE atas
-- paket yang sama.
--
-- Jalankan sebagai SYSTEM SETELAH 01-03. Idempoten.
-- =====================================================================

ALTER SESSION SET CONTAINER = FREEPDB1;

-- Buat akun operator bila belum ada (idempoten: abaikan ORA-01920 "user exists").
DECLARE
  v_ada NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_ada FROM dba_users WHERE username = 'RAG_OPERATOR';
  IF v_ada = 0 THEN
    EXECUTE IMMEDIATE
      'CREATE USER rag_operator IDENTIFIED BY "Rahasia_Lab_2026"';
  END IF;
END;
/

GRANT CREATE SESSION TO rag_operator;

-- Lima view yang sama dengan rag_baca - tak lebih. Operator melihat SEMUA
-- BARIS (lewat set_operator), tetapi tetap hanya lima view, tetap tanpa kolom
-- sensitif, tetap tak menyentuh tabel mentah. 'Operator' bukan 'pemilik'.
GRANT SELECT ON ncs.v_karyawan  TO rag_operator;
GRANT SELECT ON ncs.v_cuti      TO rag_operator;
GRANT SELECT ON ncs.v_lembur    TO rag_operator;
GRANT SELECT ON ncs.v_pengadaan TO rag_operator;
GRANT SELECT ON ncs.v_sppd      TO rag_operator;

-- EXECUTE atas paket scope: perlu untuk set_identity, predicate, DAN
-- set_operator. Yang membedakan rag_operator dari rag_baca bukan grant ini,
-- melainkan cek SESSION_USER di dalam set_operator (03-row-scope.sql).
GRANT EXECUTE ON ncs.rag_scope TO rag_operator;

-- Catatan produksi (di luar cakupan skrip lab): beri rag_operator profil
-- sumber daya seperti rag_baca (CONNECT_TIME, dsb.), dan simpan sandinya di
-- secret manager - bukan konstanta di berkas ini.
