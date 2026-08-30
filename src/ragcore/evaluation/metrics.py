"""Metrik lab: recall retrieval, kebocoran dokumen dicabut, kemampuan menolak."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from ragcore.domain import Document

from .. import config
from ..retrieval.retriever import retrieve_best, search_hybrid, search_vector
from .testset import matches, refusal_cases, retrieval_cases, version_cases

# Sebuah pencari: pertanyaan masuk, daftar chunks keluar.
Retriever = Callable[[str], Sequence[Document]]


def default_methods() -> list[tuple[str, Retriever]]:
    """Ketiga metode pencarian sebagai pasangan (nama, fungsi).

    Berurutan dari yang paling sederhana — itulah urutan yang dibandingkan di
    modul B6. Nama dipakai apa adanya sebagai judul di laporan.
    """
    return [
        ("VEKTOR SAJA", lambda t: search_vector(t, k=config.N_FINAL)),
        ("HYBRID", search_hybrid),
        ("HYBRID + SUSUN ULANG", retrieve_best),
    ]


def evaluate_retrieval(
    get_fn: Retriever, name: str, k: int | None = None, rinci: bool = True,
    quiet: bool = False
) -> float:
    """Recall@k satu metode pencarian, dirinci per jenis pertanyaan.

    `quiet=True` hanya mengembalikan angkanya. Dipakai recall_curve(),
    yang memanggil fungsi ini sembilan kali - tiga metode dikali tiga
    nilai k - dan tanpa itu mencetak sembilan blok rincian yang
    menenggelamkan tabel yang justru ingin dibaca.
    """
    k = k or config.N_FINAL
    all_case = retrieval_cases()

    kena = 0
    kind_per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failed: list[tuple[str, str]] = []

    for case in all_case:
        chunks = get_fn(case["tanya"])[:k]
        correct = matches(chunks, case)
        kena += correct
        kind_per[case["jenis"]][0] += correct
        kind_per[case["jenis"]][1] += 1
        if not correct:
            failed.append((case["jenis"], case["tanya"]))

    recall = kena / len(all_case)
    if quiet:
        return recall
    print(f"\n=== {name} ===")
    print(f"  recall@{k} keseluruhan : {recall:.0%}  ({kena}/{len(all_case)})")
    for kind in sorted(kind_per):
        kind_correct, kind_total = kind_per[kind]
        print(f"    {kind:16s} {kind_correct}/{kind_total}")
    if failed and rinci:
        print("  yang terlewat:")
        for kind, query_text in failed:
            print(f"    [{kind}] {query_text}")
    return recall


# Nilai k yang dilaporkan berdampingan. Lihat recall_curve().
CURVE_K: tuple[int, ...] = (1, 2, 4)


def recall_curve(ks: tuple[int, ...] = CURVE_K) -> dict[str, dict[int, float]]:
    """Recall ketiga metode pada BEBERAPA nilai k sekaligus.

    KENAPA SATU ANGKA TIDAK CUKUP. Korpus lab ini hanya 41 chunks. Dengan
    k=4, hampir sepersepuluh korpus ikut dikembalikan, dan ketiga metode
    sama-sama mencapai 100% - laporan yang terlihat sempurna dan tidak
    mengajarkan apa-apa. Perbedaannya tidak hilang; ia tertutup oleh k yang
    terlalu longgar untuk korpus sekecil ini.

    Diukur pada set uji yang sama, korpus yang sama:

        metode                  @1    @2    @4
        vektor saja            93%   96%  100%
        hybrid                 89%   96%  100%
        hybrid + susun ulang   93%  100%  100%

    Bacanya: pada k=1 HYBRID JUSTRU LEBIH BURUK daripada vektor saja.
    Pencarian leksikal melebarkan kumpulan kandidat, dan pelebaran itu
    membawa masuk chunks yang cocok katanya tetapi salah maksudnya.
    Yang mengubah pelebaran menjadi ketepatan adalah SUSUN ULANG - bukan
    hybrid-nya sendiri.

    Itu pelajaran yang hilang seluruhnya bila hanya recall@4 yang dilaporkan,
    dan ia berlawanan dengan dugaan kebanyakan orang. Karena itu kurva ini
    dicetak, bukan satu angka.
    """
    result: dict[str, dict[int, float]] = {}
    for k in ks:
        for name, fn in default_methods():
            result.setdefault(name, {})[k] = evaluate_retrieval(
                fn, name, k=k, quiet=True)

    width = max(len(n) for n in result)
    print()
    print("  " + "metode".ljust(width) + "".join(f"{'@' + str(k):>7}" for k in ks))
    print("  " + "-" * (width + 7 * len(ks)))
    for name, per_k in result.items():
        print("  " + name.ljust(width)
              + "".join(f"{per_k[k]:>7.0%}" for k in ks))
    print()
    print("  Bila ketiga baris sama di k terbesar, itu bukan bukti ketiganya")
    print("  setara - hanya tanda k-nya terlalu longgar untuk korpus ini.")
    return result


def compare_methods(k: int | None = None) -> dict[str, float]:
    """Jalankan ketiga metode pada set uji yang sama, lalu ringkas hasilnya.

    Inilah bentuk perbaikan yang bisa dipertanggungjawabkan: angka sebelum dan
    sesudah, pada set uji yang sama.
    """
    k = k or config.N_FINAL
    result = {name: evaluate_retrieval(fn, name, k=k) for name, fn in default_methods()}

    print("\n" + "=" * 52)
    print("RINGKASAN")
    for name, recall in result.items():
        print(f"  {name:24s} recall@{k} = {recall:.0%}")
    print("=" * 52)
    print("Inilah bentuk perbaikan yang bisa dipertanggungjawabkan:")
    print("angka sebelum dan sesudah, pada set uji yang sama.")
    return result


def evaluate_status_filter() -> tuple[int, int] | None:
    """Ukur manfaat penyaringan metadata status — inti modul B3.

    Jebakan korpus: SOP-03 (DICABUT) dan SOP-05 (BERLAKU) saling bertentangan.
    Recall biasa tidak menangkapnya — kedua dokumen sama-sama 'relevan' menurut
    kesamaan makna. Yang berbahaya adalah dokumen yang sudah dicabut IKUT masuk
    ke konteks, karena model lalu bisa menjawab dari aturan yang tidak berlaku.

    Metrik ini menghitung, untuk pertanyaan bertipe 'versi', berapa kali dokumen
    dicabut bocor ke dalam chunks yang diambil — dengan dan tanpa filters.
    Tidak memanggil model: cukup memeriksa metadata chunks.
    """
    case = version_cases()
    if not case:
        print("\n  Tidak ada kasus 'versi' di set uji.")
        return None

    def exists_revoked(chunks: Sequence[Document]) -> bool:
        return any(d.metadata.get("status") == config.REVOKED_STATUS for d in chunks)

    print(f"\n=== PENYARINGAN STATUS — {len(case)} kasus versi (B3) ===")
    leaks_without = leaks_with = 0
    for x in case:
        # filters={} -> tanpa filters apa pun; filters=None -> filter bawaan 'berlaku'
        exists_without = exists_revoked(retrieve_best(x["tanya"], filters={}))
        exists_with = exists_revoked(retrieve_best(x["tanya"]))
        leaks_without += exists_without
        leaks_with += exists_with
        print(
            f"  tanpa filter: {'DICABUT bocor' if exists_without else 'aman':13s}"
            f" | dengan filter: {'DICABUT bocor' if exists_with else 'aman':13s}"
            f" | {x['tanya']}"
        )

    print("\n  dokumen dicabut masuk konteks:")
    print(f"    tanpa penyaring  : {leaks_without}/{len(case)}")
    print(f"    dengan penyaring : {leaks_with}/{len(case)}")
    print("  Penyaringan status inilah yang mencegah jawaban SALAH SECARA")
    print("  ORGANISASI (mis. '8 karakter' dari SOP yang sudah dicabut) —")
    print("  bukan sekadar kurang tepat. Ditegakkan di kode, bukan di prompt.")
    return leaks_without, leaks_with


def evaluate_refusal() -> float | None:
    """Menguji apakah sistem BERANI berkata tidak tahu.

    Sistem yang tidak pernah menolak adalah sistem yang selalu mengarang saat
    konteksnya tidak memadai — dan itu jauh lebih berbahaya daripada sistem
    yang sesekali menjawab 'tidak ditemukan'.

    Satu-satunya metrik di modul ini yang memanggil model bahasa, jadi juga
    yang paling lambat.
    """
    from ..generation.answerer import answer

    case = refusal_cases()
    if not case:
        print("\n  Tidak ada kasus penolakan di set uji. Tambahkan.")
        return None

    correct = 0
    print(f"\n=== KEMAMPUAN MENOLAK ({len(case)} kasus) ===")
    for x in case:
        content, _, _ = answer(x["tanya"], show_chunks=False)
        refuses = config.NOT_FOUND in content
        correct += refuses
        print(f"  {'MENOLAK ' if refuses else 'MENJAWAB'}  {x['tanya']}")
        if not refuses:
            print(f"            -> {content[:90]}...")
    print(f"  benar menolak: {correct}/{len(case)} ({correct / len(case):.0%})")
    return correct / len(case)
