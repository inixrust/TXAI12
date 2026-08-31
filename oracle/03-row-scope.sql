-- =====================================================================
-- Lapisan 5: penyaringan BARIS per-unit (Oracle VPD) untuk user LOGIN.
--
-- Lapisan 1-4 (02-restrictions.sql) menahan TULIS, menyembunyikan KOLOM
-- sensitif, membatasi sumber daya, dan mencatat audit - tapi setiap baris
-- tetap terbaca siapa pun yang tersambung. Itu benar untuk pemakaian OPERATOR
-- (audit lintas-unit). Tapi begitu USER biasa bertanya lewat agent, ia tak
-- boleh membaca data unit lain - sama seperti RLS dokumen: staf Divisi TI tak
-- melihat baris Divisi SDM.
--
-- Prinsipnya sama dengan sebelumnya: PENEGAKAN DI BASIS DATA, bukan di prompt.
-- VPD menempelkan predikat WHERE ke SETIAP query view - apa pun SQL yang ditulis
-- model, Oracle menyaringnya. Model tak bisa melewatinya.
--
-- Kebijakan: user melihat barisnya UNITnya sendiri; 'Direksi' melihat semua
-- (pengawasan/audit lintas-unit). Identitas diambil dari NIP yang SUDAH
-- terverifikasi aplikasi, dan unitnya DITURUNKAN DARI TABEL di sini - bukan
-- dipercaya dari pemanggil.
--
-- PERTAHANAN BERLAPIS (temuan pentest F-02): begitu identitas pemohon terpin
-- di sesi (set_identity), eskalasi 'lihat semua' (set_operator) DITOLAK di
-- basis data - jadi validator SELECT-tunggal di aplikasi bukan lagi
-- satu-satunya penghalang. Lihat set_operator di bawah.
-- =====================================================================

ALTER SESSION SET CONTAINER = FREEPDB1;

-- v_sppd sebelumnya tak punya kolom `unit` (hanya golongan) - ditambahkan agar
-- bisa disaring per-unit seperti view lainnya. Kolom sensitif tetap tak ada.
CREATE OR REPLACE VIEW ncs.v_sppd AS
SELECT s.nomor_sppd, k.nama, k.golongan, k.unit, s.tujuan, s.jenis_tujuan,
       s.tanggal_ajuan, s.tanggal_berangkat, s.tanggal_kembali,
       s.tanggal_laporan, s.jabatan_penyetuju, s.keterangan
FROM   ncs.sppd s JOIN ncs.karyawan k ON k.nip = s.nip;
GRANT SELECT ON ncs.v_sppd TO rag_baca;


-- Paket tepercaya: SATU-SATUNYA jalan mengisi konteks rag_ctx (lihat CREATE
-- CONTEXT ... USING di bawah). rag_baca punya EXECUTE di sini, tapi TIDAK bisa
-- memanggil DBMS_SESSION.SET_CONTEXT langsung untuk rag_ctx.
CREATE OR REPLACE PACKAGE ncs.rag_scope AS
  PROCEDURE set_identity(p_nip VARCHAR2);
  PROCEDURE set_operator;
  FUNCTION  predicate(p_schema VARCHAR2, p_object VARCHAR2) RETURN VARCHAR2;
END rag_scope;
/
CREATE OR REPLACE PACKAGE BODY ncs.rag_scope AS

  PROCEDURE set_identity(p_nip VARCHAR2) IS
    v_unit ncs.karyawan.unit%TYPE;
  BEGIN
    -- Unit DITURUNKAN dari tabel, otoritatif - bukan dipercaya dari pemanggil.
    SELECT unit INTO v_unit FROM ncs.karyawan WHERE nip = p_nip;
    DBMS_SESSION.SET_CONTEXT('rag_ctx', 'unit', v_unit);
    DBMS_SESSION.SET_CONTEXT('rag_ctx', 'scope_all',
                             CASE WHEN v_unit = 'Direksi' THEN 'Y' ELSE 'N' END);
    -- PIN sesi ke sebuah identitas terverifikasi. Ini mematikan set_operator
    -- (lihat di bawah): sekali agent menyetel identitas pemohon, tak ada lagi
    -- eskalasi 'lihat semua' yang bisa dipanggil dari SQL model.
    DBMS_SESSION.SET_CONTEXT('rag_ctx', 'pinned', 'Y');
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      -- NIP tak dikenal -> tak melihat apa pun (fail-closed).
      DBMS_SESSION.SET_CONTEXT('rag_ctx', 'unit', NULL);
      DBMS_SESSION.SET_CONTEXT('rag_ctx', 'scope_all', 'N');
      DBMS_SESSION.SET_CONTEXT('rag_ctx', 'pinned', 'Y');
  END set_identity;

  PROCEDURE set_operator IS
    v_user VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');
  BEGIN
    -- Konteks operator/maintenance (CLI, BUKAN web anonim): lihat semua.
    --
    -- PENUTUPAN PENUH F-02 (oracle/04-operator-account.sql) - LAPIS PERTAMA:
    -- hanya AKUN operator tepercaya yang boleh 'lihat semua'. Akun query
    -- rag_baca DITOLAK di sini. Ini menutup residu yang ditemukan pentest:
    -- pin (lapis kedua di bawah) hanya menahan eskalasi dari jalur APLIKASI,
    -- tetapi kredensial rag_baca yang menyambung LANGSUNG pada sesi SEGAR
    -- (pinned masih kosong) dulu masih bisa set_operator. Dengan cek akun ini,
    -- set_operator gagal untuk rag_baca APA PUN keadaan sesinya. Pemisahan
    -- dilakukan DI DALAM prosedur karena EXECUTE paket all-or-nothing: kedua
    -- akun ber-EXECUTE atas rag_scope (perlu untuk set_identity/predicate),
    -- jadi hanya set_operator sendiri yang bisa membedakannya.
    IF v_user NOT IN ('RAG_OPERATOR', 'NCS', 'SYSTEM') THEN
      RAISE_APPLICATION_ERROR(
        -20003,
        'set_operator ditolak: akun ' || v_user || ' bukan operator');
    END IF;
    -- PERTAHANAN BERLAPIS - LAPIS KEDUA (jalur aplikasi). Begitu identitas
    -- pemohon terpin di sesi (set_identity dipanggil guard SEBELUM tiap query),
    -- eskalasi 'lihat semua' DITOLAK - walau validator aplikasi tertembus dan
    -- `EXEC ncs.rag_scope.set_operator` sampai ke basis data lewat sesi
    -- operator, ia gagal dan penyaringan per-unit tetap berlaku.
    IF SYS_CONTEXT('rag_ctx', 'pinned') = 'Y' THEN
      RAISE_APPLICATION_ERROR(
        -20002,
        'set_operator ditolak: sesi sudah terpin ke identitas pemohon');
    END IF;
    DBMS_SESSION.SET_CONTEXT('rag_ctx', 'scope_all', 'Y');
  END set_operator;

  FUNCTION predicate(p_schema VARCHAR2, p_object VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    IF SYS_CONTEXT('rag_ctx', 'scope_all') = 'Y' THEN
      RETURN NULL;                        -- tanpa batas (Direksi/operator)
    ELSIF SYS_CONTEXT('rag_ctx', 'unit') IS NOT NULL THEN
      RETURN 'unit = SYS_CONTEXT(''rag_ctx'',''unit'')';
    ELSE
      RETURN '1=0';                       -- fail-closed: identitas belum diset
    END IF;
  END predicate;

END rag_scope;
/

-- Konteks rag_ctx HANYA bisa diisi dari dalam paket ncs.rag_scope.
CREATE OR REPLACE CONTEXT rag_ctx USING ncs.rag_scope;

GRANT EXECUTE ON ncs.rag_scope TO rag_baca;


-- Pasang VPD di kelima view. Idempoten: buang kebijakan lama dulu bila ada.
DECLARE
  TYPE t_views IS TABLE OF VARCHAR2(30);
  v_views t_views := t_views('V_KARYAWAN', 'V_CUTI', 'V_LEMBUR',
                             'V_PENGADAAN', 'V_SPPD');
BEGIN
  FOR i IN 1 .. v_views.COUNT LOOP
    BEGIN
      DBMS_RLS.DROP_POLICY('NCS', v_views(i), 'RAG_UNIT_' || v_views(i));
    EXCEPTION
      WHEN OTHERS THEN NULL;             -- belum ada -> lewati
    END;
    DBMS_RLS.ADD_POLICY(
      object_schema   => 'NCS',
      object_name     => v_views(i),
      policy_name     => 'RAG_UNIT_' || v_views(i),
      function_schema => 'NCS',
      policy_function => 'RAG_SCOPE.PREDICATE',
      statement_types => 'SELECT');
  END LOOP;
END;
/
