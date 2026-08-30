"""Menjalankan set uji dan mencetak hasilnya.

Dipisah dari penilaian karena inilah yang paling sering disunting saat
mengajar — kolom, urutan, bacaan di bawah tabel — dan perubahan tampilan
tidak boleh berisiko menyentuh logika penilaian.

compare_runs() ada karena satu angka tanpa pembanding tidak berarti apa-apa
pada model yang tidak deterministik.
"""
from __future__ import annotations

import json
from collections import defaultdict

from ragcore import config
from ragcore.evaluation.hybrid import tools_called, tools_correct
from ragcore.evaluation.scoring import (
    degenerate_output,
    score_answer,
    unusable_result,
)


def _print_conditions(case_per: dict) -> None:
    """Sebutkan kondisi yang memproduksi angka di bawahnya.

    ANGKA TANPA KONDISINYA BUKAN HASIL PENGUKURAN, MELAINKAN ANGKA SAJA.

    Bawaan lab adalah qwen3:8b, tetapi hampir semua pengukuran saat lab ini
    disusun dijalankan pada qwen3:4b - karena 8b tumpah ke CPU pada kartu 6 GB
    dan memakan sekitar enam menit per kasus. Keduanya sah; yang TIDAK sah
    adalah melaporkan "jawaban benar 73%" tanpa menyebut yang mana.

    Akibatnya nyata bagi peserta: ia menjalankan perintah yang sama dengan
    konfigurasi bawaan, mendapat angka yang berbeda jauh, dan menyimpulkan
    ada yang rusak pada pemasangannya. Padahal yang berbeda hanya modelnya.

    num_ctx ikut dicetak karena ia PERNAH menjadi penyebab senyap: bawaan
    Ollama 4096 memotong prompt sistem tanpa errors apa pun, dan seluruh angka
    yang diukur sebelum itu ketahuan tidak dapat dipakai. Lihat
    config.NUM_CTX_CHAT.
    """

    again = max((len(v) for v in case_per.values()), default=1)
    print()
    print(f"  diukur pada    : {config.MODEL_CHAT} "
          f"(num_ctx {config.NUM_CTX_CHAT})")
    print(f"  penyimpanan    : {config.STORAGE}")
    print(f"  kasus x ulangan: {len(case_per)} x {again}")
    if again == 1:
        print("  CATATAN: satu ulangan tidak dapat memisahkan perbaikan dari")
        print("           kebisingan. Pakai --ulang 2 atau lebih.")


HISTORY = "evaluation-history.json"


def _key(case: dict) -> str:
    return f"{case.get('pengguna') or '-'}|{case['tanya'][:60]}"


def compare_runs(case_per: dict) -> list[tuple[str, str, str]]:
    """Kasus yang hasilnya BERBEDA dari run sebelumnya.

    KENAPA INI PERLU, PADAHAL SUDAH ADA `--ulang`.

    `--ulang` menandai GOYAH ketika ulangan berbeda DI DALAM satu run. Ia
    buta terhadap bentuk yang lebih licik: dua ulangan sepakat satu sama
    lain, lalu pasangan berikutnya di run lain menghasilkan sesuatu yang
    sama sekali berbeda - dan keduanya tampak stabil.

    Terjadi saat lab ini disusun, dan penyusunnya tertipu. Kelompok
    `pengecualian` diukur empat kali dengan hasil 0%, 67%, 50%, 0%; tiga di
    antaranya TIDAK menandai apa pun sebagai goyah. Dari ayunan itu sempat
    disimpulkan hubungan sebab-akibat yang ternyata tidak ada.

    Karena itu hasil tiap kasus disimpan, dan run berikutnya
    membandingkannya. Kasus yang berpindah hasil antar-run diberi tahu -
    sekalipun di dalam masing-masing run ia terlihat stabil.
    """


    file = config.ROOT / HISTORY
    old = {}
    if file.exists():
        try:
            old = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}

    current = {}
    for content in case_per.values():
        case = content[0][0]
        pattern = "".join(("AJ" if a and b else "A-" if a else "-J" if b else "--")
                       for _, a, b in content)
        current[_key(case)] = pattern

    berpindah = [(k, old[k], current[k]) for k in current
                 if k in old and old[k] != current[k]]

    file.write_text(json.dumps(current, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    return berpindah


def report(case_per_result) -> dict:
    """hasil_per_kasus: daftar (kasus, pesan_pesan, jawaban)."""
    kind_per = defaultdict(lambda: {"n": 0, "alat": 0, "jawab": 0})
    # Hasil tiap kasus dikumpulkan per identitas kasus, bukan sekadar
    # dijumlahkan. Dengan --ulang, satu kasus muncul beberapa kali; kalau
    # hasilnya TIDAK SAMA di antara ulangan, angka rata-ratanya menyesatkan
    # dan yang justru perlu dilaporkan adalah kegoyahannya.
    case_per = defaultdict(list)
    rusak: list = []
    berhenti: list = []
    meleset = []

    for case, message, answer_text in case_per_result:
        j = kind_per[case["jenis"]]
        j["n"] += 1
        tool_ok = tools_correct(case, tools_called(message))
        answer_ok, reason = score_answer(answer_text, case)
        j["alat"] += tool_ok
        j["jawab"] += answer_ok
        case_per[(case.get("pengguna"), case["tanya"])].append(
            (case, bool(tool_ok), bool(answer_ok)))
        if unusable_result(answer_text):
            berhenti.append(case)
        elif degenerate_output(answer_text):
            rusak.append(case)
        if not (tool_ok and answer_ok):
            meleset.append((case, tool_ok, reason))

    _print_conditions(case_per)
    print(f"\n  {'jenis':<16}{'n':>4}{'alat':>8}{'jawaban':>9}")
    print("  " + "-" * 37)
    total = {"n": 0, "alat": 0, "jawab": 0}
    for kind, a in sorted(kind_per.items()):
        print(f"  {kind:<16}{a['n']:>4}{a['alat']/a['n']:>8.0%}"
              f"{a['jawab']/a['n']:>9.0%}")
        for k in total:
            total[k] += a[k]
    print("  " + "-" * 37)
    print(f"  {'SELURUHNYA':<16}{total['n']:>4}"
          f"{total['alat']/total['n']:>8.0%}{total['jawab']/total['n']:>9.0%}")

    if berhenti:
        print()
        print(f"  {len(berhenti)} jalan BERHENTI DI TENGAH "
              "(lewat batas waktu atau errors):")
        for case in berhenti[:6]:
            print(f"    [{case['jenis']}] {case['tanya'][:56]}")
        if len(berhenti) > 6:
            print(f"    ... dan {len(berhenti) - 6} lagi")
        print("  Ini BUKAN jawaban salah. Naikkan --batas-detik, atau")
        print("  pakai model yang lebih cepat.")

    if rusak:
        print()
        print(f"  {len(rusak)} jalan menghasilkan KELUARAN RUSAK, "
              "bukan jawaban salah:")
        for case in rusak[:6]:
            print(f"    [{case['jenis']}] {case['tanya'][:56]}")
        if len(rusak) > 6:
            print(f"    ... dan {len(rusak) - 6} lagi")
        print("  Ini kegagalan BENTUK: model berhenti berperilaku "
              "seperti agent.")
        print("  Menyetel prompt tidak menolong. Kurangi jumlah tool, "
              "atau pakai")
        print("  model yang lebih besar.")

    goyah = [(v[0][0], v) for v in case_per.values()
             if len(v) > 1 and len({(x, y) for _, x, y in v}) > 1]
    if goyah:
        print()
        print(f"  {len(goyah)} kasus GOYAH - hasilnya berubah antar ulangan.")
        print("  Angka di atas TIDAK bisa dipakai menilai perubahan prompt;")
        print("  yang terukur di kasus ini adalah kebisingan, bukan mutu.")
        for case, round_no in goyah:
            pattern = " ".join(("AJ" if x and y else "A-" if x else
                             "-J" if y else "--") for _, x, y in round_no)
            print(f"    [{case['jenis']}] {case['tanya'][:52]}")
            print(f"        {pattern}   (A=alat tepat, J=jawaban benar)")

    if meleset:
        print(f"\n  {len(meleset)} kasus meleset:")
        for case, tool_ok, reason in meleset:
            cause = []
            if not tool_ok:
                cause.append("salah pilih alat")
            if reason:
                cause.append(reason)
            print(f"    [{case['jenis']}] {case['tanya'][:58]}")
            print(f"        -> {', '.join(cause)}")

    pindah = compare_runs(case_per)
    if pindah:
        print()
        print(f"  {len(pindah)} kasus BERBEDA DARI RUN SEBELUMNYA:")
        for key, dulu, kini in pindah[:8]:
            print(f"    {dulu:>6} -> {kini:<6}  {key.split('|')[1][:48]}")
        print("  Kasus ini terlihat stabil DI DALAM tiap run, tetapi berayun")
        print("  antar-run. Jangan memakainya menilai perubahan apa pun.")

    _read_gap(total, goyah=len(goyah), case=len(case_per),
                  berhenti=len(berhenti),
                  rusak=len(rusak))
    return dict(kind_per)


def _read_gap(total: dict, goyah: int = 0, case: int = 0,
                  rusak: int = 0, berhenti: int = 0) -> None:
    """Terjemahkan hasil evaluasi menjadi saran perbaikan.

    `goyah` = banyaknya kasus yang hasilnya berubah antar ulangan,
    `kasus` = banyaknya kasus berbeda yang diuji.
    """
    if not total["n"]:
        return
    tool = total["alat"] / total["n"]
    answer = total["jawab"] / total["n"]

    gap = tool - answer
    print("\n  Bacaan:")
    # Dibaca dari SELISIH, bukan dua ambang mutlak. Alat 77% dan jawaban 40%
    # adalah jurang 37 poin yang jelas artinya — tetapi aturan lama menuntut
    # alat >= 80%, jadi ia melewatkannya dan melaporkan "kedua metrik
    # sejalan". Ambang mutlak menyembunyikan justru kasus yang paling
    # sering terjadi.
    # KASUS YANG BERHENTI DI TENGAH DIBACA LEBIH DULU LAGI.
    #
    # Kasus yang tidak pernah selesai tidak mengukur mutu apa pun. Selama
    # sebagiannya berhenti, angka di atas adalah angka dari sebagian
    # kasus saja - dan sebagian itu tidak dipilih secara acak, melainkan
    # justru kasus yang paling berat.
    if total["n"] and berhenti / total["n"] >= 0.1:
        print(f"    {berhenti} dari {total['n']} jalan BERHENTI di tengah.")
        print("    Yang lewat batas cenderung kasus terberat, jadi angka")
        print("    di atas condong optimis. Naikkan --batas-detik, atau")
        print("    pakai model yang lebih cepat, lalu ukur ulang.")
        return

    # KELUARAN RUSAK DIDAHULUKAN DARI SEGALANYA.
    #
    # Selama model masih menuliskan panggilan tool sebagai teks atau
    # mengembalikan kosong, ia tidak sedang menjawab dengan buruk - ia
    # tidak sedang menjawab. Selisih dua metrik, kegoyahan, dan seluruh
    # saran prompt di bawah ini tidak berlaku pada keadaan itu.
    if total["n"] and rusak / total["n"] >= 0.1:
        print(f"    {rusak} dari {total['n']} jalan menghasilkan keluaran")
        print("    RUSAK, bukan jawaban salah. Selesaikan itu lebih dulu:")
        print("    kurangi jumlah tool, atau naikkan ukuran model.")
        print("    Menyetel prompt tidak akan mengubah angka ini.")
        return

    # KEGOYAHAN DIDAHULUKAN. Selisih dua metrik hanya berarti bila
    # angkanya stabil. Kalau seperempat kasus memberi hasil berbeda tiap
    # kali dijalankan, yang terbaca dari selisih itu sebagian besar
    # undian - dan menyetel prompt berdasarkan undian adalah cara paling
    # rapi untuk merasa maju tanpa maju.
    if case and goyah / case >= 0.2:
        print(f"    {goyah} dari {case} kasus GOYAH. Stabilkan dulu,")
        print("    baru baca angkanya. Selisih dua metrik tidak berarti")
        print("    apa-apa selama hasilnya berubah tiap kali dijalankan.")
        print("    Mulai dari kasus yang polanya paling sering berganti.")
        return

    if gap >= 0.25:
        print("    Pemilihan sumber sudah benar, penalarannya yang gagal.")
        print("    Perbaiki prompt penyusunan jawaban - bukan deskripsi tool.")
    elif gap <= -0.25:
        print("    Jawaban benar tanpa memanggil sumber yang seharusnya.")
        print("    Ini TIDAK akan bertahan di korpus yang lebih besar.")
        print("    Periksa apakah model menjawab dari hafalan, bukan dari data.")
    elif tool < 0.6 and answer < 0.6:
        print("    Keduanya rendah - mulai dari deskripsi tool.")
        print("    Model tidak bisa memilih apa yang tidak ia pahami bedanya.")
    elif answer < 0.8:
        # Ambang mutlak DIPERLUKAN di sini. Sebelumnya cabang ini jatuh
        # ke "kedua metrik sejalan, buatlah kasus yang lebih sulit" pada
        # alat 73% / jawaban 55% - menyarankan mempersulit ujian kepada
        # sistem yang masih salah menjawab hampir separuh soalnya.
        # Selisih kecil di angka rendah berarti keduanya sama-sama
        # buruk, bukan keduanya sudah baik.
        print(f"    Jawaban benar baru {answer:.0%} - terlalu rendah untuk")
        print("    disebut sejalan. Selisihnya memang kecil, tetapi itu")
        print("    karena keduanya sama-sama rendah, bukan karena sudah")
        print("    baik. Baca daftar kasus meleset dan kerjakan yang")
        print("    sebabnya paling sering berulang.")
    else:
        print("    Kedua metrik sejalan dan sudah tinggi. Perbaikan")
        print("    berikutnya menuntut kasus uji yang lebih sulit,")
        print("    bukan penyetelan prompt.")
