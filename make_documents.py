"""Pembangkit dokumen SOP fiktif berbahasa Indonesia untuk lab RAG.
Perusahaan fiktif: PT Nusantara Cipta Solusi (NCS).
Setiap 'jangkar' dicatat nomor halamannya, lalu diekspor ke testset.json
sehingga evaluasi retrieval punya kunci jawaban yang benar-benar akurat."""
import json
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documents")
MAP = {}   # (berkas, jangkar) -> halaman

S = getSampleStyleSheet()
def st(n, **kw):
    dasar = dict(fontName="Helvetica", fontSize=9.5, leading=14, spaceAfter=5)
    dasar.update(kw)
    return ParagraphStyle(n, parent=S["Normal"], **dasar)

TITLE   = st("j", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=3, alignment=1)
SUBTITLE  = st("sj", fontSize=10, leading=13, alignment=1, spaceAfter=14, textColor=colors.HexColor("#444444"))
CHAPTER     = st("bab", fontName="Helvetica-Bold", fontSize=11, leading=15, spaceBefore=12, spaceAfter=6)
ARTICLE   = st("psl", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=9, spaceAfter=3)
CONTENT     = st("isi", alignment=4)
CLAUSE    = st("ayat", alignment=4, leftIndent=14)
NOTE = st("cat", fontSize=8.5, textColor=colors.HexColor("#666666"), spaceBefore=8)


class Anchor(Flowable):
    """Flowable tak terlihat yang mencatat di halaman berapa ia dirender."""
    def __init__(self, file, name):
        Flowable.__init__(self); self.file = file; self.name = name
        self.width = 0; self.height = 0
    def draw(self):
        MAP[(self.file, self.name)] = self.canv.getPageNumber()


class Doc(BaseDocTemplate):
    def __init__(self, path, kop, **kw):
        BaseDocTemplate.__init__(self, path, pagesize=A4,
                                 leftMargin=22*mm, rightMargin=22*mm,
                                 topMargin=24*mm, bottomMargin=20*mm, **kw)
        self.kop = kop
        f = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="n")
        self.addPageTemplates(PageTemplate(id="p", frames=f, onPage=self.decorate))
    def decorate(self, c, d):
        c.saveState()
        c.setFont("Helvetica", 7); c.setFillColor(colors.HexColor("#888888"))
        c.drawString(22*mm, A4[1]-15*mm, self.kop)
        c.drawRightString(A4[0]-22*mm, A4[1]-15*mm, "PT Nusantara Cipta Solusi")
        c.setStrokeColor(colors.HexColor("#cccccc")); c.setLineWidth(.4)
        c.line(22*mm, A4[1]-17*mm, A4[0]-22*mm, A4[1]-17*mm)
        c.line(22*mm, 15*mm, A4[0]-22*mm, 15*mm)
        c.drawString(22*mm, 11*mm, "Dokumen internal — dilarang diperbanyak tanpa izin")
        c.drawRightString(A4[0]-22*mm, 11*mm, "Hal. %d" % c.getPageNumber())
        c.restoreState()


def table(data, width):
    t = Table(data, colWidths=width, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 8.5),
        ("FONT", (0,1), (-1,-1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#222222")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
        ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    return t

# ============================================================ SOP-01 KEPEGAWAIAN
def sop_hr():
    B = "SOP-01-Kepegawaian.pdf"
    e = []
    e += [Paragraph("STANDAR OPERASIONAL PROSEDUR", TITLE),
          Paragraph("PENGELOLAAN KEPEGAWAIAN", TITLE),
          Paragraph("Nomor: SOP-01/NCS/HRD/2026 &nbsp;&nbsp;|&nbsp;&nbsp; Berlaku sejak: 5 Januari 2026", SUBTITLE)]
    e += [table([["Disusun oleh","Diperiksa oleh","Disahkan oleh"],
                 ["Divisi SDM","Kepala Divisi SDM","Direktur Utama"],
                 ["Andini Prasetya","Bramantyo Wijaya","Chandra Halim"]],
                [52*mm,52*mm,52*mm]), Spacer(1,12)]

    e += [Paragraph("BAB I — KETENTUAN UMUM", CHAPTER), Paragraph("Pasal 1 — Maksud dan Tujuan", ARTICLE),
          Paragraph("(1) Prosedur ini disusun sebagai pedoman baku pengelolaan kepegawaian "
                    "di lingkungan PT Nusantara Cipta Solusi, selanjutnya disebut Perusahaan.", CLAUSE),
          Paragraph("(2) Prosedur ini berlaku bagi seluruh karyawan tetap, karyawan kontrak, "
                    "dan tenaga alih daya yang bekerja di seluruh unit kerja Perusahaan.", CLAUSE),
          Paragraph("Pasal 2 — Definisi", ARTICLE),
          Paragraph("(1) Karyawan tetap adalah pekerja yang terikat Perjanjian Kerja Waktu "
                    "Tidak Tertentu dan telah menyelesaikan masa percobaan.", CLAUSE),
          Paragraph("(2) Karyawan kontrak adalah pekerja yang terikat Perjanjian Kerja Waktu "
                    "Tertentu dengan jangka waktu yang telah ditetapkan.", CLAUSE),
          Paragraph("(3) SIMPEG adalah Sistem Informasi Kepegawaian, yaitu aplikasi internal "
                    "yang digunakan untuk seluruh proses administrasi kepegawaian.", CLAUSE),
          Paragraph("(4) SPPD adalah Surat Perintah Perjalanan Dinas, yaitu dokumen resmi yang "
                    "menjadi dasar penugasan karyawan ke luar kota.", CLAUSE)]

    e += [Anchor(B, "masa_percobaan")]
    e += [Paragraph("BAB II — MASA PERCOBAAN DAN PENGANGKATAN", CHAPTER),
          Paragraph("Pasal 3 — Masa Percobaan", ARTICLE),
          Paragraph("(1) Setiap karyawan baru yang diterima sebagai calon karyawan tetap wajib "
                    "menjalani masa percobaan selama <b>3 (tiga) bulan</b> terhitung sejak "
                    "tanggal mulai bekerja.", CLAUSE),
          Paragraph("(2) Selama masa percobaan, karyawan berhak atas upah penuh sesuai golongan "
                    "jabatan, namun belum berhak atas tunjangan kinerja triwulanan.", CLAUSE),
          Paragraph("(3) Ketentuan pada ayat (1) tidak berlaku bagi karyawan yang diangkat "
                    "melalui jalur alih status dari tenaga alih daya yang telah bekerja "
                    "sekurang-kurangnya 12 (dua belas) bulan berturut-turut.", CLAUSE),
          Paragraph("(4) Masa percobaan tidak dapat diperpanjang.", CLAUSE),
          Paragraph("Pasal 4 — Evaluasi dan Pengangkatan", ARTICLE),
          Paragraph("(1) Evaluasi masa percobaan dilakukan oleh atasan langsung pada minggu "
                    "kesebelas dan disampaikan kepada Divisi SDM paling lambat 5 (lima) hari "
                    "kerja sebelum masa percobaan berakhir.", CLAUSE),
          Paragraph("(2) Karyawan yang dinyatakan lulus evaluasi diangkat menjadi karyawan tetap "
                    "melalui Surat Keputusan Direktur Utama.", CLAUSE)]

    e += [PageBreak(), Anchor(B, "cuti")]
    e += [Paragraph("BAB III — CUTI DAN IZIN", CHAPTER),
          Paragraph("Pasal 5 — Cuti Tahunan", ARTICLE),
          Paragraph("(1) Karyawan yang telah bekerja sekurang-kurangnya 12 (dua belas) bulan "
                    "berturut-turut berhak atas cuti tahunan selama <b>12 (dua belas) hari "
                    "kerja</b> dalam satu tahun.", CLAUSE),
          Paragraph("(2) Hak cuti tahunan sebagaimana dimaksud pada ayat (1) tidak dapat "
                    "diuangkan dan gugur apabila tidak digunakan sampai dengan 31 Maret "
                    "tahun berikutnya.", CLAUSE),
          Paragraph("(3) Pengambilan cuti tahunan secara berturut-turut lebih dari 5 (lima) hari "
                    "kerja wajib memperoleh persetujuan Kepala Divisi.", CLAUSE),
          Paragraph("Pasal 6 — Prosedur Pengajuan Cuti", ARTICLE),
          Paragraph("(1) Pengajuan cuti dilakukan melalui aplikasi SIMPEG paling lambat "
                    "<b>7 (tujuh) hari kerja</b> sebelum tanggal pelaksanaan cuti.", CLAUSE),
          Paragraph("(2) Alur persetujuan pengajuan cuti adalah sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["Tahap","Pelaksana","Batas Waktu"],
                 ["Pengajuan","Karyawan","H-7 hari kerja"],
                 ["Verifikasi ketersediaan hak","Divisi SDM","1 hari kerja"],
                 ["Persetujuan","Atasan langsung","2 hari kerja"],
                 ["Persetujuan lanjutan (cuti > 5 hari)","Kepala Divisi","2 hari kerja"],
                 ["Pencatatan","Divisi SDM","1 hari kerja"]],
                [58*mm,50*mm,40*mm]),
          Spacer(1,5),
          Paragraph("(3) Pengajuan yang tidak memperoleh persetujuan dalam batas waktu "
                    "sebagaimana tabel pada ayat (2) dianggap disetujui secara otomatis "
                    "oleh sistem.", CLAUSE),
          Paragraph("Pasal 7 — Cuti Sakit dan Cuti Melahirkan", ARTICLE),
          Paragraph("(1) Cuti sakit lebih dari 2 (dua) hari kerja wajib disertai surat "
                    "keterangan dokter yang diunggah ke SIMPEG.", CLAUSE),
          Paragraph("(2) Karyawan perempuan berhak atas cuti melahirkan selama 3 (tiga) bulan "
                    "dengan upah penuh, dan dapat diperpanjang 1 (satu) bulan tanpa upah "
                    "atas persetujuan Kepala Divisi.", CLAUSE)]

    e += [PageBreak(), Anchor(B, "lembur")]
    e += [Paragraph("BAB IV — WAKTU KERJA DAN LEMBUR", CHAPTER),
          Paragraph("Pasal 8 — Waktu Kerja", ARTICLE),
          Paragraph("(1) Waktu kerja Perusahaan adalah 8 (delapan) jam sehari dan 40 (empat "
                    "puluh) jam seminggu, dari hari Senin sampai dengan Jumat, pukul 08.00 "
                    "sampai dengan 17.00 dengan istirahat 1 (satu) jam.", CLAUSE),
          Paragraph("(2) Unit kerja yang melayani operasional 24 jam dapat menerapkan sistem "
                    "kerja bergilir dengan persetujuan Direktur Operasional.", CLAUSE),
          Paragraph("Pasal 9 — Lembur", ARTICLE),
          Paragraph("(1) Lembur adalah pekerjaan yang dilaksanakan di luar waktu kerja "
                    "sebagaimana dimaksud dalam Pasal 8 ayat (1).", CLAUSE),
          Paragraph("(2) Lembur wajib memperoleh persetujuan tertulis dari <b>atasan langsung "
                    "setingkat Manajer</b> sebelum dilaksanakan, dan diajukan melalui SIMPEG.", CLAUSE),
          Paragraph("(3) Lembur yang melebihi 3 (tiga) jam dalam satu hari wajib memperoleh "
                    "persetujuan tambahan dari Kepala Divisi.", CLAUSE),
          Paragraph("(4) Lembur pada hari libur nasional wajib memperoleh persetujuan Direktur "
                    "Operasional tanpa memandang jumlah jamnya.", CLAUSE),
          Paragraph("(5) Batas maksimum lembur adalah 14 (empat belas) jam dalam satu minggu.", CLAUSE),
          Paragraph("Pasal 10 — Perhitungan Upah Lembur", ARTICLE),
          Paragraph("(1) Upah lembur dihitung berdasarkan upah sejam, yaitu 1/173 dari upah "
                    "bulanan.", CLAUSE),
          Spacer(1,3),
          table([["Kondisi","Jam ke-","Pengali"],
                 ["Hari kerja biasa","1","1,5 x upah sejam"],
                 ["Hari kerja biasa","2 dan seterusnya","2 x upah sejam"],
                 ["Hari libur mingguan","1 sampai 8","2 x upah sejam"],
                 ["Hari libur mingguan","9","3 x upah sejam"],
                 ["Hari libur nasional","1 sampai 8","2 x upah sejam"]],
                [52*mm,44*mm,52*mm]),
          Paragraph("(2) Upah lembur dibayarkan bersamaan dengan upah bulanan pada periode "
                    "penggajian berikutnya.", CLAUSE)]

    e += [Anchor(B, "tunjangan")]
    e += [Paragraph("BAB V — TUNJANGAN", CHAPTER),
          Paragraph("Pasal 11 — Jenis Tunjangan", ARTICLE),
          Paragraph("(1) Perusahaan memberikan tunjangan sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["Jenis Tunjangan","Golongan","Besaran per Bulan"],
                 ["Tunjangan jabatan","Manajer ke atas","Rp 3.500.000"],
                 ["Tunjangan jabatan","Supervisor","Rp 1.750.000"],
                 ["Tunjangan komunikasi","Seluruh karyawan tetap","Rp 250.000"],
                 ["Tunjangan makan","Seluruh karyawan","Rp 30.000 per hari kerja"]],
                [55*mm,48*mm,45*mm]),
          Paragraph("(2) Tunjangan kinerja triwulanan diberikan kepada karyawan tetap yang "
                    "memperoleh nilai kinerja sekurang-kurangnya 80 (delapan puluh).", CLAUSE),
          Paragraph("(3) Karyawan yang masih menjalani masa percobaan tidak berhak atas "
                    "tunjangan jabatan dan tunjangan kinerja triwulanan.", CLAUSE),
          Paragraph("Catatan: Perusahaan tidak menyediakan tunjangan transportasi dalam bentuk "
                    "uang tunai. Kebutuhan transportasi dinas diatur tersendiri dalam SE-12/2026 "
                    "tentang Perjalanan Dinas.", NOTE)]

    Doc(os.path.join(ROOT, "sop", B), "SOP-01/NCS/HRD/2026 — Pengelolaan Kepegawaian").build(e)
    print("dibuat:", B)

# ============================================================ SOP-02 PENGADAAN
def sop_procurement():
    B = "SOP-02-Pengadaan.pdf"
    e = []
    e += [Paragraph("STANDAR OPERASIONAL PROSEDUR", TITLE),
          Paragraph("PENGADAAN BARANG DAN JASA", TITLE),
          Paragraph("Nomor: SOP-02/NCS/PRC/2026 &nbsp;&nbsp;|&nbsp;&nbsp; Berlaku sejak: 12 Januari 2026", SUBTITLE)]
    e += [Paragraph("BAB I — KETENTUAN UMUM", CHAPTER),
          Paragraph("Pasal 1 — Ruang Lingkup", ARTICLE),
          Paragraph("(1) Prosedur ini mengatur pengadaan barang dan jasa untuk keperluan "
                    "operasional seluruh unit kerja Perusahaan.", CLAUSE),
          Paragraph("(2) Pengadaan yang bersumber dari dana proyek pelanggan diatur tersendiri "
                    "dalam perjanjian kerja sama dengan pelanggan yang bersangkutan.", CLAUSE)]

    e += [Anchor(B, "batas_nilai")]
    e += [Paragraph("BAB II — KEWENANGAN DAN METODE", CHAPTER),
          Paragraph("Pasal 2 — Batas Nilai dan Kewenangan Persetujuan", ARTICLE),
          Paragraph("(1) Kewenangan persetujuan pengadaan ditetapkan berdasarkan nilai "
                    "sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["Nilai Pengadaan","Metode","Pemberi Persetujuan"],
                 ["Sampai Rp 10.000.000","Pembelian langsung","Kepala Unit Kerja"],
                 ["Rp 10.000.001 – Rp 100.000.000","Permintaan penawaran","Kepala Divisi"],
                 ["Rp 100.000.001 – Rp 500.000.000","Seleksi terbatas","Direktur Keuangan"],
                 ["Di atas Rp 500.000.000","Seleksi terbuka","Direktur Utama"]],
                [50*mm,42*mm,56*mm]),
          Paragraph("(2) Pemecahan nilai pengadaan dengan maksud menghindari kewenangan "
                    "persetujuan yang lebih tinggi dilarang dan dikenakan sanksi disiplin.", CLAUSE),
          Paragraph("Pasal 3 — Permintaan Penawaran", ARTICLE),
          Paragraph("(1) Metode permintaan penawaran mensyaratkan sekurang-kurangnya "
                    "<b>3 (tiga) penawaran</b> dari penyedia yang berbeda.", CLAUSE),
          Paragraph("(2) Apabila hanya tersedia kurang dari 3 (tiga) penyedia yang memenuhi "
                    "syarat teknis, Unit Pengadaan wajib membuat berita acara penjelasan "
                    "yang disetujui Direktur Keuangan.", CLAUSE)]

    e += [PageBreak(), Anchor(B, "alur")]
    e += [Paragraph("BAB III — ALUR PROSES", CHAPTER),
          Paragraph("Pasal 4 — Tahapan Pengadaan", ARTICLE),
          Paragraph("(1) Tahapan pengadaan barang dan jasa adalah sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["No","Tahapan","Penanggung Jawab","Jangka Waktu"],
                 ["1","Pengajuan kebutuhan","Unit pemohon","-"],
                 ["2","Verifikasi anggaran","Divisi Keuangan","2 hari kerja"],
                 ["3","Penyusunan spesifikasi teknis","Unit pemohon","3 hari kerja"],
                 ["4","Permintaan penawaran","Unit Pengadaan","5 hari kerja"],
                 ["5","Evaluasi penawaran","Tim Evaluasi","3 hari kerja"],
                 ["6","Penetapan penyedia","Sesuai kewenangan","2 hari kerja"],
                 ["7","Penerbitan Purchase Order","Unit Pengadaan","1 hari kerja"],
                 ["8","Penerimaan dan pemeriksaan","Unit pemohon","Sesuai kontrak"],
                 ["9","Pembayaran","Divisi Keuangan","14 hari kerja"]],
                [12*mm,60*mm,42*mm,34*mm]),
          Paragraph("(2) Purchase Order yang telah diterbitkan tidak dapat dibatalkan sepihak "
                    "kecuali penyedia melakukan wanprestasi.", CLAUSE),
          Paragraph("Pasal 5 — Pembayaran", ARTICLE),
          Paragraph("(1) Pembayaran dilakukan paling lambat <b>14 (empat belas) hari kerja</b> "
                    "setelah barang atau jasa diterima lengkap dan faktur pajak diterima "
                    "Divisi Keuangan.", CLAUSE),
          Paragraph("(2) Pembayaran uang muka paling banyak 30% (tiga puluh persen) dari nilai "
                    "kontrak dan hanya untuk pengadaan di atas Rp 100.000.000.", CLAUSE)]

    e += [Anchor(B, "penyedia")]
    e += [Paragraph("BAB IV — PENYEDIA", CHAPTER),
          Paragraph("Pasal 6 — Persyaratan Penyedia", ARTICLE),
          Paragraph("(1) Penyedia wajib memenuhi persyaratan berikut:", CLAUSE),
          Paragraph("a. memiliki Nomor Induk Berusaha yang masih berlaku;", CLAUSE),
          Paragraph("b. memiliki Nomor Pokok Wajib Pajak dan tidak memiliki tunggakan pajak;", CLAUSE),
          Paragraph("c. tidak sedang dalam daftar hitam Perusahaan; dan", CLAUSE),
          Paragraph("d. memiliki pengalaman pekerjaan sejenis sekurang-kurangnya 2 (dua) tahun "
                    "untuk pengadaan di atas Rp 100.000.000.", CLAUSE),
          Paragraph("Pasal 7 — Daftar Hitam", ARTICLE),
          Paragraph("(1) Penyedia dimasukkan ke dalam daftar hitam apabila terbukti melakukan "
                    "wanprestasi, memberikan dokumen palsu, atau menawarkan gratifikasi "
                    "kepada karyawan Perusahaan.", CLAUSE),
          Paragraph("(2) Masa berlaku daftar hitam adalah 2 (dua) tahun sejak ditetapkan.", CLAUSE)]

    Doc(os.path.join(ROOT, "sop", B), "SOP-02/NCS/PRC/2026 — Pengadaan Barang dan Jasa").build(e)
    print("dibuat:", B)


# ============================================================ SE-12 PERJALANAN DINAS
def se_travel():
    B = "SE-12-2026-Perjalanan-Dinas.pdf"
    e = []
    e += [Paragraph("SURAT EDARAN", TITLE),
          Paragraph("PENYELENGGARAAN PERJALANAN DINAS", TITLE),
          Paragraph("Nomor: SE-12/NCS/DIR/2026 &nbsp;&nbsp;|&nbsp;&nbsp; Berlaku sejak: 1 Februari 2026", SUBTITLE),
          Paragraph("Kepada seluruh Kepala Divisi dan Kepala Unit Kerja di lingkungan "
                    "PT Nusantara Cipta Solusi.", CONTENT),
          Spacer(1,8)]

    e += [Anchor(B, "sppd")]
    e += [Paragraph("BAB I — SURAT PERINTAH PERJALANAN DINAS", CHAPTER),
          Paragraph("Pasal 1 — Ketentuan SPPD", ARTICLE),
          Paragraph("(1) Setiap perjalanan dinas wajib didahului dengan penerbitan Surat "
                    "Perintah Perjalanan Dinas (SPPD) melalui aplikasi SIMPEG.", CLAUSE),
          Paragraph("(2) SPPD diajukan paling lambat <b>3 (tiga) hari kerja</b> sebelum "
                    "keberangkatan.", CLAUSE),
          Paragraph("(3) SPPD untuk perjalanan dinas mendadak dapat diajukan paling lambat "
                    "1 (satu) hari kerja sebelum keberangkatan dengan persetujuan lisan "
                    "Kepala Divisi yang dikonfirmasi tertulis dalam 2 (dua) hari kerja "
                    "setelahnya.", CLAUSE),
          Paragraph("(4) Perjalanan dinas tanpa SPPD tidak dapat direimbursasi.", CLAUSE),
          Paragraph("Pasal 2 — Kewenangan Persetujuan SPPD", ARTICLE),
          Spacer(1,3),
          table([["Tujuan Perjalanan","Pemberi Persetujuan"],
                 ["Dalam satu provinsi","Kepala Unit Kerja"],
                 ["Luar provinsi, dalam negeri","Kepala Divisi"],
                 ["Luar negeri","Direktur Utama"]],
                [76*mm,72*mm])]

    e += [PageBreak(), Anchor(B, "biaya")]
    e += [Paragraph("BAB II — KOMPONEN BIAYA", CHAPTER),
          Paragraph("Pasal 3 — Uang Harian", ARTICLE),
          Paragraph("(1) Uang harian perjalanan dinas ditetapkan sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["Golongan","Dalam Provinsi","Luar Provinsi","Luar Negeri"],
                 ["Direksi","Rp 600.000","Rp 900.000","USD 120"],
                 ["Kepala Divisi","Rp 450.000","Rp 700.000","USD 95"],
                 ["Manajer","Rp 350.000","Rp 550.000","USD 80"],
                 ["Staf","Rp 250.000","Rp 400.000","USD 65"]],
                [37*mm,37*mm,37*mm,37*mm]),
          Paragraph("(2) Uang harian mencakup biaya makan, transportasi lokal, dan pengeluaran "
                    "pribadi selama perjalanan dinas.", CLAUSE),
          Paragraph("(3) Uang harian dibayarkan penuh untuk perjalanan dinas yang melewati "
                    "pukul 00.00, dan setengah untuk perjalanan dinas yang berakhir pada "
                    "hari yang sama.", CLAUSE),
          Paragraph("Pasal 4 — Penginapan dan Transportasi", ARTICLE),
          Paragraph("(1) Batas biaya penginapan per malam adalah sebagai berikut:", CLAUSE),
          Spacer(1,3),
          table([["Golongan","Dalam Provinsi","Luar Provinsi"],
                 ["Direksi","Rp 1.500.000","Rp 2.000.000"],
                 ["Kepala Divisi","Rp 1.000.000","Rp 1.400.000"],
                 ["Manajer","Rp 750.000","Rp 1.000.000"],
                 ["Staf","Rp 500.000","Rp 700.000"]],
                [49*mm,49*mm,50*mm]),
          Paragraph("(2) Moda transportasi udara kelas ekonomi berlaku untuk seluruh golongan, "
                    "kecuali Direksi untuk penerbangan di atas 5 (lima) jam.", CLAUSE),
          Paragraph("Pasal 5 — Pertanggungjawaban", ARTICLE),
          Paragraph("(1) Laporan pertanggungjawaban perjalanan dinas beserta bukti pengeluaran "
                    "diserahkan paling lambat <b>5 (lima) hari kerja</b> setelah kembali.", CLAUSE),
          Paragraph("(2) Keterlambatan penyerahan laporan mengakibatkan penundaan penerbitan "
                    "SPPD berikutnya untuk karyawan yang bersangkutan.", CLAUSE)]

    Doc(os.path.join(ROOT, "edaran", B), "SE-12/NCS/DIR/2026 — Perjalanan Dinas").build(e)
    print("dibuat:", B)

# ================================================ SOP-03 KEAMANAN INFORMASI (DICABUT)
def sop_security_revoked():
    B = "SOP-03-Keamanan-Informasi-DICABUT.pdf"
    e = []
    e += [Paragraph("STANDAR OPERASIONAL PROSEDUR", TITLE),
          Paragraph("KEAMANAN INFORMASI", TITLE),
          Paragraph("Nomor: SOP-03/NCS/TI/2024 &nbsp;&nbsp;|&nbsp;&nbsp; "
                    "<b>DICABUT</b> — digantikan SOP-05/NCS/TI/2026", SUBTITLE)]
    e += [table([["STATUS DOKUMEN"],
                 ["DICABUT sejak 1 Maret 2026 melalui SK-08/NCS/DIR/2026."],
                 ["Dokumen ini disimpan untuk keperluan arsip dan audit."],
                 ["Ketentuan di dalamnya TIDAK BERLAKU lagi."]], [156*mm]),
          Spacer(1,12)]
    e += [Anchor(B, "sandi_lama")]
    e += [Paragraph("BAB I — PENGELOLAAN KATA SANDI", CHAPTER),
          Paragraph("Pasal 1 — Ketentuan Kata Sandi", ARTICLE),
          Paragraph("(1) Kata sandi akun sistem internal sekurang-kurangnya terdiri atas "
                    "<b>8 (delapan) karakter</b>.", CLAUSE),
          Paragraph("(2) Kata sandi wajib diganti setiap <b>90 (sembilan puluh) hari</b>.", CLAUSE),
          Paragraph("(3) Autentikasi dua faktor bersifat opsional dan dianjurkan untuk akun "
                    "dengan hak akses administrator.", CLAUSE),
          Paragraph("Pasal 2 — Perangkat Kerja", ARTICLE),
          Paragraph("(1) Karyawan diperbolehkan menggunakan perangkat pribadi untuk mengakses "
                    "surat elektronik Perusahaan.", CLAUSE),
          Paragraph("(2) Penyimpanan dokumen Perusahaan pada layanan awan pihak ketiga "
                    "diperbolehkan sepanjang memperoleh izin lisan atasan.", CLAUSE)]
    Doc(os.path.join(ROOT, "sop", B), "SOP-03/NCS/TI/2024 — DICABUT").build(e)
    print("dibuat:", B)


# ================================================ SOP-05 KEAMANAN INFORMASI (BERLAKU)
def sop_security_new():
    B = "SOP-05-Keamanan-Informasi.pdf"
    e = []
    e += [Paragraph("STANDAR OPERASIONAL PROSEDUR", TITLE),
          Paragraph("KEAMANAN INFORMASI", TITLE),
          Paragraph("Nomor: SOP-05/NCS/TI/2026 &nbsp;&nbsp;|&nbsp;&nbsp; Berlaku sejak: 1 Maret 2026", SUBTITLE),
          Paragraph("Prosedur ini menggantikan SOP-03/NCS/TI/2024 yang dinyatakan dicabut "
                    "melalui SK-08/NCS/DIR/2026.", CONTENT), Spacer(1,8)]
    e += [Anchor(B, "sandi_baru")]
    e += [Paragraph("BAB I — PENGELOLAAN AKSES", CHAPTER),
          Paragraph("Pasal 1 — Ketentuan Kata Sandi", ARTICLE),
          Paragraph("(1) Kata sandi akun sistem internal sekurang-kurangnya terdiri atas "
                    "<b>14 (empat belas) karakter</b> dan memuat kombinasi huruf besar, "
                    "huruf kecil, angka, serta karakter khusus.", CLAUSE),
          Paragraph("(2) Kata sandi <b>tidak lagi diwajibkan diganti secara berkala</b>, dan "
                    "hanya wajib diganti apabila terdapat indikasi kebocoran.", CLAUSE),
          Paragraph("(3) Autentikasi dua faktor bersifat <b>wajib</b> bagi seluruh akun yang "
                    "dapat mengakses data pelanggan atau data kepegawaian.", CLAUSE),
          Paragraph("Pasal 2 — Perangkat Kerja", ARTICLE),
          Paragraph("(1) Akses terhadap sistem internal hanya diperbolehkan melalui perangkat "
                    "yang terdaftar dan dikelola Divisi TI.", CLAUSE),
          Paragraph("(2) Penggunaan perangkat pribadi untuk mengakses data Perusahaan "
                    "<b>dilarang</b>, termasuk untuk surat elektronik.", CLAUSE),
          Paragraph("(3) Penyimpanan dokumen Perusahaan pada layanan awan pihak ketiga "
                    "<b>dilarang</b> tanpa persetujuan tertulis Kepala Divisi TI.", CLAUSE)]
    e += [Anchor(B, "insiden")]
    e += [Paragraph("BAB II — PENANGANAN INSIDEN", CHAPTER),
          Paragraph("Pasal 3 — Pelaporan Insiden", ARTICLE),
          Paragraph("(1) Setiap dugaan insiden keamanan informasi wajib dilaporkan kepada "
                    "Divisi TI paling lambat <b>1 (satu) jam</b> setelah diketahui.", CLAUSE),
          Paragraph("(2) Pelaporan dilakukan melalui saluran darurat yang tersedia 24 jam.", CLAUSE),
          Spacer(1,3),
          table([["Tingkat","Kriteria","Waktu Tanggap"],
                 ["Kritis","Data pelanggan bocor keluar Perusahaan","1 jam"],
                 ["Tinggi","Akses tidak sah ke sistem produksi","4 jam"],
                 ["Sedang","Perangkat hilang tanpa data sensitif","1 hari kerja"],
                 ["Rendah","Percobaan serangan yang berhasil dicegah","3 hari kerja"]],
                [26*mm,78*mm,44*mm])]
    Doc(os.path.join(ROOT, "sop", B), "SOP-05/NCS/TI/2026 — Keamanan Informasi").build(e)
    print("dibuat:", B)


# ============================================================ NOTULEN (Markdown)
def minutes():
    content = """# Notulen Rapat Koordinasi Divisi TI

**Nomor:** NR-04/NCS/TI/2026
**Tanggal:** 18 Maret 2026, pukul 09.00 - 11.15
**Tempat:** Ruang Rapat Nusantara, Lantai 4

## Peserta

Bramantyo Wijaya (Kepala Divisi TI), Dewi Anggraini (Manajer Infrastruktur),
Eko Saputro (Manajer Aplikasi), Fitria Ramadhani (Manajer Keamanan),
Gunawan Halim (Staf Infrastruktur).

## Agenda 1 - Evaluasi Penerapan SOP-05

Fitria Ramadhani melaporkan bahwa penerapan SOP-05/NCS/TI/2026 tentang Keamanan
Informasi telah berjalan sejak 1 Maret 2026. Tingkat kepatuhan autentikasi dua
faktor mencapai 78 persen dari total akun yang diwajibkan.

Kendala utama adalah karyawan lapangan yang belum memiliki perangkat terdaftar.
Diputuskan Divisi TI akan menyediakan 40 unit perangkat tambahan pada triwulan
kedua tahun 2026.

Bramantyo Wijaya menegaskan bahwa ketentuan larangan penggunaan perangkat pribadi
tidak dapat ditawar, dan meminta Divisi SDM menyampaikan pengumuman ulang kepada
seluruh unit kerja.

## Agenda 2 - Migrasi Aplikasi SIMPEG

Eko Saputro menyampaikan bahwa migrasi SIMPEG ke versi 3 dijadwalkan selesai pada
30 Juni 2026. Modul yang paling terdampak adalah pengajuan cuti dan pengajuan SPPD.

Selama masa migrasi, pengajuan cuti tetap mengikuti ketentuan SOP-01/NCS/HRD/2026,
yaitu paling lambat 7 hari kerja sebelum pelaksanaan. Tidak ada perubahan batas waktu.

Dewi Anggraini mengingatkan bahwa capacity storage server saat ini tersisa
32 persen, dan mengusulkan pengadaan storage tambahan mengikuti SOP-02/NCS/PRC/2026.
Nilai perkiraan Rp 180.000.000, sehingga memerlukan persetujuan Direktur Keuangan.

## Agenda 3 - Rencana Uji Coba Sistem Tanya Jawab Dokumen

Eko Saputro mengusulkan uji coba sistem tanya jawab berbasis dokumen internal untuk
membantu karyawan mencari ketentuan pada SOP tanpa harus membaca seluruh dokumen.

Fitria Ramadhani menekankan bahwa sistem tersebut wajib berjalan sepenuhnya di
lingkungan internal Perusahaan. Tidak diperbolehkan mengirim isi dokumen ke layanan
kecerdasan buatan pihak ketiga di luar Perusahaan.

Diputuskan uji coba dilaksanakan pada triwulan ketiga tahun 2026 dengan lingkup awal
dokumen kepegawaian dan pengadaan.

## Keputusan Rapat

1. Divisi TI menyediakan 40 unit perangkat terdaftar pada triwulan kedua 2026.
2. Divisi SDM menyampaikan pengumuman ulang ketentuan SOP-05 kepada seluruh unit.
3. Migrasi SIMPEG versi 3 diselesaikan paling lambat 30 Juni 2026.
4. Pengadaan storage tambahan diajukan dengan persetujuan Direktur Keuangan.
5. Uji coba sistem tanya jawab dokumen dilaksanakan pada triwulan ketiga 2026.
"""
    p = os.path.join(ROOT, "notulen", "NR-04-2026-Rapat-Koordinasi-TI.md")
    open(p, "w", encoding="utf-8").write(content)
    print("dibuat: NR-04-2026-Rapat-Koordinasi-TI.md")


if __name__ == "__main__":
    sop_hr(); sop_procurement(); se_travel()
    sop_security_revoked(); sop_security_new(); minutes()
    print("\n--- peta jangkar (berkas, jangkar) -> halaman ---")
    for k, v in sorted(MAP.items()):
        print(f"  {k[0]:45s} {k[1]:16s} hal.{v}")
    # Ditulis di samping folder dokumen, BUKAN di /tmp.
    #
    # Sebelumnya berkas ini ditulis ke jalur POSIX /tmp/peta_jangkar.json.
    # Di Windows jalur itu menunjuk ke folder tmp di akar drive C, yang ada
    # di sebagian mesin dan tidak ada di sebagian lain. Yang punya: berkasnya
    # nyasar ke luar folder lab dan tidak pernah ditemukan. Yang tidak punya:
    # FileNotFoundError di BARIS TERAKHIR, setelah seluruh PDF selesai
    # dibangun - kerja yang benar, dilaporkan sebagai gagal.
    mapping = Path(ROOT).parent / 'peta_jangkar.json'
    mapping.write_text(
        json.dumps({f'{a}|{b}': h for (a, b), h in MAP.items()}, indent=1),
        encoding='utf-8')
    print()
    print(f'  peta jangkar -> {mapping}')
