"""Identitas users dan hak aksesnya (L6 lanjutan).

Modul ini menjawab pertanyaan yang di TX-AI11 tidak pernah ada: SIAPA yang
sedang bertanya, dan atas dasar apa sistem boleh menampilkan sesuatu
kepadanya.

TIGA LAPIS, DAN URUTANNYA DISENGAJA
-----------------------------------

  1. Identitas   - siapa dia. Datang dari login, bukan dari pertanyaan.
  2. Penyaring   - apa yang PANTAS ditampilkan. Berjalan di aplikasi, mudah
                   dibaca, mudah diuji, dan mudah pula dilupakan.
  3. RLS         - apa yang BOLEH dibaca. Berjalan di basis data, berlaku
                   pada setiap query termasuk yang lupa menyaring.

Lapis 2 tanpa lapis 3 adalah harapan. Lapis 3 tanpa lapis 2 tetap benar,
hanya kurang enak dipakai — users melihat "tidak ditemukan" tanpa tahu
bahwa yang dicarinya memang ada tetapi bukan haknya.

JEBAKAN YANG PALING PENTING
---------------------------
Nilai `unit` TIDAK BOLEH berasal dari pertanyaan users, dari parameter
URL, atau dari apa pun yang bisa dipengaruhi model. Ia datang dari sesi
login. Kalau model bisa memengaruhinya, RLS hanya MEMINDAHKAN lubangnya —
dari "aplikasi lupa menyaring" menjadi "model dibujuk mengaku unit lain".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import quote

from ragcore import config

# Nama unit yang sah: huruf, angka, spasi, titik, hubung. Sengaja SEMPIT.
# Ini batas kepercayaan antara identitas users dan URL sambungan Postgres —
# lihat connection_for().
_UNIT_OK = re.compile(r"[\w .\-]{1,64}", re.UNICODE)

# Peran. Sengaja hanya dua: yang menambah lebih banyak peran daripada yang
# benar-benar dibedakan perlakuannya justru membuat hak akses sulit diaudit.
STAFF_ROLE = "staf"
MANAGER_ROLE = "pimpinan"

# Unit yang BERWENANG meninjau vonis kepatuhan yang ditahan alur Konsultasi
# (human-in-the-loop, L10). Divisi SDM memiliki SOP kepegawaian (SOP-01:
# "disusun Divisi SDM, disahkan Direktur Utama"); Direksi mengesahkan. Unit
# lain - TERMASUK IT - tidak meninjau vonis kebijakan: mereka MEMAKAI sistemnya,
# bukan MEMILIKI putusannya. Di produksi ini datang dari peran IdP/tabel
# kepegawaian, bukan daftar unit di kode.
REVIEWER_UNITS = ("Direksi", "Divisi SDM")


@dataclass(frozen=True)
class User:
    """Identitas yang dibawa sepanjang satu sesi."""

    nip: str
    name: str
    unit: str
    role: str = STAFF_ROLE

    @property
    def manager(self) -> bool:
        return self.role == MANAGER_ROLE

    def __str__(self) -> str:
        return f"{self.name} ({self.unit}, {self.role})"


class _Public:
    """Identitas ANONIM - hanya dokumen umum, lewat sambungan NON-PEMILIK.

    Ini yang membedakannya dari `None`, dan bedanya kritis:

        None   -> sambungan PEMILIK tabel, KEBAL RLS. Hanya untuk indexing dan
                  pemeliharaan. Diberikan ke request = melihat SEMUA dokumen.
        PUBLIC -> sambungan peran aplikasi TANPA unit. RLS menyisakan hanya
                  klasifikasi='umum'. Aman untuk akses tanpa login.

    Anonim yang diberi None bukan melihat lebih sedikit, melainkan lebih
    BANYAK - itulah lubang yang ditemukan saat auth API dipasang. PUBLIC ada
    supaya "tanpa login" punya jalur yang benar, bukan meminjam jalur pemilik.
    """

    unit = None
    manager = False

    def __repr__(self) -> str:                       # untuk pesan/log terbaca
        return "PUBLIC"


# Satu instance dipakai bersama; dibandingkan dengan `is`.
PUBLIC = _Public()


# Daftar users lab. Di sistem sungguhan ini datang dari LDAP, SSO, atau
# tabel kepegawaian — BUKAN dari daftar di dalam kode. Nama dan unitnya
# sengaja diambil dari tabel karyawan Oracle supaya lab Hari 3 nyambung:
# users yang login adalah orang yang sama dengan yang datanya ditanyakan.
REGISTRY: dict[str, User] = {
    "NCS-0012": User("NCS-0012", "Andini Prasetya", "Divisi SDM", STAFF_ROLE),
    "NCS-0023": User("NCS-0023", "Budi Santoso", "Divisi TI", STAFF_ROLE),
    "NCS-0031": User("NCS-0031", "Sinta Rahmawati", "Divisi TI", MANAGER_ROLE),
    "NCS-0068": User("NCS-0068", "Fitri Handayani", "Divisi Pengadaan", STAFF_ROLE),
    "NCS-0007": User("NCS-0007", "Bramantyo Wijaya", "Divisi SDM", MANAGER_ROLE),
    "NCS-0001": User("NCS-0001", "Chandra Halim", "Direksi", MANAGER_ROLE),
}

# Kata sandi lab, sama untuk semua. Disimpan sebagai hash supaya bentuk
# kodenya benar sejak awal — bukan karena hash SHA-256 polos ini aman untuk
# produksi. Untuk produksi: bcrypt, scrypt, atau argon2, dengan salt.
_LAB_PASSWORD = hashlib.sha256(b"lab2026").hexdigest()


def login(nip: str, password: str) -> User | None:
    """Kembalikan Pengguna bila NIP dan sandinya cocok, None bila tidak."""
    person = REGISTRY.get((nip or "").strip().upper())
    if person is None:
        return None
    if hashlib.sha256(password.encode()).hexdigest() != _LAB_PASSWORD:
        return None
    return person


def demo_users() -> list[User]:
    """Semua users, diurutkan — untuk pemilih di ui kelas."""
    return sorted(REGISTRY.values(), key=lambda p: (p.unit, p.name))


def is_reviewer(person: object) -> bool:
    """Apakah orang ini BERWENANG menyetujui vonis kepatuhan yang ditahan?

    Peran yang MEMILIKI kebijakan: pimpinan Divisi SDM (pemilik SOP kepegawaian)
    atau Direksi. Staf tidak; unit lain - termasuk IT - tidak. Ini separuh dari
    pemisahan tugas; separuh lain ditegakkan di UI: si PENANYA tak boleh
    menyetujui vonisnya sendiri, sekalipun ia kebetulan seorang peninjau.

    PUBLIC, None, dan bentuk dict lama bukan peninjau (fail-closed) - hanya
    User sungguhan dengan peran pimpinan di unit yang berwenang.
    """
    return (isinstance(person, User)
            and person.manager
            and person.unit in REVIEWER_UNITS)


# ---------------------------------------------------------------- sambungan

def connection_for(person: User | None) -> str:
    """URL sambungan yang sudah membawa identitas unit users.

    Identitas dititipkan lewat parameter `options` koneksi PostgreSQL, jadi
    ia melekat pada SESI — bukan pada query yang harus diingat menyertakannya.
    Setiap SELECT pada sesi itu, termasuk pencarian vektor dan termasuk query
    yang lupa menyaring, sudah tersaring kebijakan RLS.

    TIGA JALUR, DAN JANGAN TERTUKAR:

      None    -> sambungan PEMILIK tabel (kebal RLS). Hanya indexing dan
                 pemeliharaan; SALAH untuk melayani pertanyaan.
      PUBLIC  -> sambungan peran aplikasi TANPA unit. RLS menyisakan hanya
                 klasifikasi='umum'. Inilah tier "tanpa login" yang AMAN.
      User    -> peran aplikasi DENGAN unit. RLS: umum + dokumen unitnya.
    """
    if person is None:
        return config.PG_URL

    if person is PUBLIC:
        # Peran non-pemilik, tanpa parameter unit. GUC app.unit_pengguna tidak
        # disetel, jadi current_setting(...) bernilai NULL dan kebijakan RLS
        # `klasifikasi='umum' OR unit=current_setting(...)` hanya meloloskan
        # baris umum. Non-pemilik, jadi RLS memang berlaku - berbeda dari None.
        return config.PG_URL_APP

    # person.unit DISUSUN ke dalam URL sambungan, jadi ia adalah batas
    # kepercayaan. Hari ini nilainya datang dari REGISTRY yang di-hardcode dan
    # aman - tetapi modul ini SENDIRI mendokumentasikan bahwa di produksi ia
    # datang dari LDAP/SSO/tabel kepegawaian. Begitu itu terjadi, satu nilai
    # unit yang mengandung '&' bisa menyuntik parameter libpq tambahan:
    #
    #   "Divisi TI&application_name=x"  -> parameter kedua sampai ke server
    #
    # dan parameter kueri libpq MENIMPA kredensial di URL - jalan menuju
    # sambungan pemilik tabel yang KEBAL RLS. Karena itu: fail-closed.
    unit = person.unit or ""
    if not _UNIT_OK.fullmatch(unit):
        raise ValueError(
            f"Nilai unit {unit!r} di luar karakter yang diizinkan "
            f"(huruf, angka, spasi, titik, hubung). Ditolak sebelum "
            f"menyentuh URL sambungan - lihat connection_for().")

    # DUA lapis escaping, dan keduanya perlu:
    #   1. parser `options` libpq memisah argumen pada spasi -> spasi (dan
    #      backslash) harus di-escape dengan backslash lebih dulu.
    #   2. hasilnya masih menjadi nilai di dalam URL -> quote() untuk lapis URL.
    # Validasi di atas menjamin tidak ada '&', '=', atau '%' yang tersisa,
    # jadi quote() bekerja pada masukan yang sudah bersih.
    for_libpq = unit.replace("\\", "\\\\").replace(" ", "\\ ")
    value = quote(for_libpq, safe="")
    separator = "&" if "?" in config.PG_URL_APP else "?"
    return (f"{config.PG_URL_APP}{separator}"
            f"options=-c%20{quote(config.GUC_UNIT, safe='')}%3D{value}")


def filter_for(person: User | None) -> dict:
    """Penyaring metadata di tingkat APLIKASI (lapis 2).

    Bukan pengganti RLS. Ini yang membuat hasilnya masuk akal bagi users,
    sedangkan RLS yang membuatnya AMAN. Keduanya sengaja dijalankan bersama:
    kalau suatu saat filters ini keliru dilonggarkan, RLS masih menahan.

    Pimpinan melihat seluruh klasifikasi di unitnya; staf hanya yang umum.
    """
    filters = {"status": config.ACTIVE_STATUS}
    # None (pemilik/maintenance) dan pimpinan melihat semua klasifikasi di
    # lapis aplikasi; PUBLIC dan staf dibatasi ke umum. RLS tetap menegakkan
    # di bawahnya - ini hanya membuat hasilnya masuk akal, bukan yang mengamankan.
    if person is None or getattr(person, "manager", False):
        return filters
    filters["klasifikasi"] = "umum"
    return filters
