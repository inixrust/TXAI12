"""Evaluasi hibrida: ketepatan alat dan ketepatan jawaban, terpisah (L9).

    python -m ragcore.commands.evaluate_hybrid
    python -m ragcore.commands.evaluate_hybrid --jenis hak_akses
    python -m ragcore.commands.evaluate_hybrid --batas 5     # cepat, untuk uji asap
    python -m ragcore.commands.evaluate_hybrid --batas-detik 600
    python -m ragcore.commands.evaluate_hybrid --ulang 3   # ukur kegoyahan

MENGULANG ITU BUKAN KEMEWAHAN. Model ini TIDAK deterministik meski
temperature=0, dan satu kasus yang sama bisa memberi tiga perilaku berbeda:
memanggil dua tool, memanggil satu, atau menuliskan panggilan tool sebagai
teks JSON mentah. Menilai perubahan prompt dari satu kali jalan berarti
mengukur kebisingan dan menyebutnya perbaikan. `--ulang` menjalankan tiap
kasus beberapa kali dan menandai yang hasilnya berubah-ubah sebagai GOYAH.

Dua angka, bukan satu. Selisih di antaranya yang memberi tahu apa yang
perlu diperbaiki — lihat docstring ragcore.evaluasi.hibrida.

KASUS HAK AKSES DIJALANKAN SEBAGAI ORANG YANG BERBEDA. Pertanyaan yang
sama punya jawaban benar yang berbeda tergantung siapa yang bertanya, jadi
agent-nya dibangun ulang per users. Itu memang lebih lambat; tanpa itu
seluruh kasus hak akses kehilangan artinya.
"""
from __future__ import annotations

import asyncio
import sys
import time

from ragcore import config
from ragcore.agent.hybrid import cleanup_orphan_mcp, hybrid_agent
from ragcore.agent.tools_hybrid import ACTIVE_USER
from ragcore.evaluation import hybrid as evaluation

from ._args import wants_help

# BATAS WAKTU PER KASUS — bukan kemewahan, melainkan syarat agar evaluasi
# bisa dipercaya sebagai proses otomatis.
#
# Terjadi saat set uji ini dijalankan penuh pertama kali: satu kasus berjalan
# 25 menit tanpa selesai (rata-rata kasus lain 4 menit), dan SELURUH evaluasi
# berhenti di situ. Bukan karena melingkar di basis data — tracing audit Oracle
# hanya mencatat 4 query sepanjang itu — melainkan model yang menghasilkan
# sangat lambat.
#
# Evaluasi yang bisa tergantung selamanya pada satu kasus tidak bisa
# dijadwalkan, tidak bisa masuk CI, dan tidak bisa ditinggal. Kasus yang
# lewat batas dihitung GAGAL, dan itu jawaban yang benar: jawaban yang tidak
# pernah datang memang tidak berguna bagi users.
SECONDS_LIMIT = 420

# Ukuran model tempat BATAS_DETIK di atas diukur: qwen3:4b, sekitar 2,5 GB.
GB_REFERENCE_SIZE = 2.5


def model_size_gb(model: str) -> float | None:
    """Ukuran model menurut Ollama, dalam GB. None bila tidak terjawab."""
    import json
    import urllib.request


    dasar = config.OLLAMA_URL or "http://localhost:11434"
    try:
        with urllib.request.urlopen(f"{dasar}/api/tags", timeout=5) as r:
            listing = json.load(r).get("models", [])
    except Exception:
        return None
    for m in listing:
        if m.get("name") == model or m.get("name", "").split(":")[0] == model:
            return m.get("size", 0) / 1e9 or None
    return None


def auto_timeout_seconds(model: str | None = None) -> int:
    """Batas waktu per kasus, DISKALAKAN menurut ukuran model.

    KENAPA TIDAK BOLEH SATU ANGKA TETAP.

    BATAS_DETIK = 420 diukur pada qwen3:4b, yang muat di VRAM kartu 6 GB dan
    menyelesaikan kasus tipikal dalam 90 detik. Tetapi BAWAAN lab ini adalah
    qwen3:8b - dua kali lipat besarnya, tumpah ke CPU pada kartu yang sama,
    dan diukur di lab ini memakan 273 sampai 369 detik untuk satu kasus yang
    hanya butuh DUA panggilan tool.

    Dengan batas tetap 420 detik, peserta yang memakai konfigurasi bawaan akan
    melihat kasus-kasus berat lewat batas secara rutin. Semuanya dihitung
    gagal, dan angkanya terbaca sebagai "model bawaan lab buruk" - padahal
    yang salah adalah batas yang disetel untuk model lain.

    Lebih buruk lagi: yang lewat batas justru kasus TERBERAT, jadi angka yang
    tersisa condong optimis. Kesalahannya tidak acak, ia berpihak.

    Penskalaannya linear terhadap ukuran model, dengan lantai di angka acuan.
    Ini batas ATAS, bukan perkiraan waktu - tujuannya menghentikan kasus yang
    menggantung, bukan menebak berapa lama yang wajar.

    BATAS_DETIK di lingkungan tetap menang, dan --batas-detik menang atas
    keduanya.
    """
    import os


    if os.getenv("BATAS_DETIK"):
        return int(os.environ["BATAS_DETIK"])

    size = model_size_gb(model or config.MODEL_CHAT)
    if not size:
        return SECONDS_LIMIT
    faktor = max(1.0, size / GB_REFERENCE_SIZE)
    return int(SECONDS_LIMIT * faktor)

# Batas langkah agent. Melindungi dari lingkaran panggilan tool, yang gagal
# dengan cara berbeda dari kelambatan dan pantas dibedakan.
STEP_LIMIT = 15


def _group(case_case: list) -> dict:
    """Kelompokkan kasus per users, supaya agent cukup dibangun sekali
    untuk tiap identitas. None = tanpa login (jalur pemeliharaan)."""
    mapping: dict = {}
    for k in case_case:
        mapping.setdefault(k.get("pengguna"), []).append(k)
    return mapping


async def run(kind: str | None = None, limit: int | None = None,
                   seconds_limit: int | None = None, again: int = 1) -> int:

    # Dibersihkan SEBELUM mulai, bukan sesudah. Sisa dari run yang dihentikan
    # paksa akan memakan RAM sepanjang evaluasi ini dan membuat angkanya
    # lebih buruk daripada semestinya — lihat cleanup_orphan_mcp().
    cleanup_orphan_mcp()

    if seconds_limit is None:
        seconds_limit = auto_timeout_seconds()
    print(f"  batas waktu per kasus: {seconds_limit} detik "
          f"({config.MODEL_CHAT})")

    case_case = [k for k in evaluation.TEST_SET
                   if kind is None or k["jenis"] == kind]
    if limit:
        case_case = case_case[:limit]
    if not case_case:
        print(f"Tidak ada kasus berjenis '{kind}'.")
        return 1

    per_users = _group(case_case)
    print(f"  {len(case_case)} kasus uji, {len(per_users)} identitas")

    # SATU sesi MCP untuk seluruh evaluasi, bukan satu per identitas.
    #
    # Identitas hanya memengaruhi sisi DOKUMEN (lewat PENGGUNA_AKTIF dan RLS
    # pgvector); sisi Oracle memakai akun hanya-baca yang sama untuk semua.
    # Membangun agent per identitas berarti menyalakan server MCP baru tiap
    # kali - masing-masing sebuah JVM ~1,4 GB.
    #
    # Terasa saat set uji ini dijalankan: server MCP dari percobaan yang
    # dihentikan tertinggal hidup, RAM bebas turun dari 6,9 GB ke 4,1 GB,
    # model chat makin tumpah ke CPU, dan kasus yang tadinya 4 menit menjadi
    # lewat batas. Evaluasi yang memakan sumber dayanya sendiri akan
    # menghasilkan angka yang makin buruk tiap kali dijalankan ulang.

    result, number = [], 0
    try:
        # operator=True: evaluasi menjalankan kasus TANPA login (person=None)
        # yang perlu 'lihat semua'. Itu jalur OPERATOR (rag_operator), bukan
        # produksi - jadi ia memakai koneksi operator, sementara /agent/ask tetap
        # rag_baca hak-minimal. Lihat oracle/04-operator-account.sql.
        async with hybrid_agent(quiet=True, operator=True) as agent:
            for group in per_users.values():
                person = evaluation.case_user(group[0])
                print(f"\n  === sebagai {person or 'tanpa login'} "
                      f"({len(group)} kasus) ===")
                ACTIVE_USER.set(person)

                for case in group:
                    number += 1
                    print(f"  [{number}/{len(case_case)}] "
                          f"({case['jenis']}) {case['tanya'][:56]}")
                    for round_no in range(again):
                        message, answer_text, seconds = await _satu_kasus(
                            agent, case, seconds_limit)
                        prefix = (f"        ulangan {round_no + 1}/{again}: "
                                  if again > 1 else "        ")
                        print(f"{prefix}{seconds:.0f} detik")
                        result.append((case, message, answer_text))
    except KeyboardInterrupt:
        # Ctrl-C di tengah evaluasi 51 menit adalah hal yang PASTI terjadi.
        # Yang sudah dikerjakan tetap dilaporkan dan disimpan; yang tidak
        # boleh terjadi adalah server MCP tertinggal hidup diam-diam.
        print(f"\n  Dihentikan setelah {len(result)} dari "
              f"{len(case_case)} kasus.")
    finally:
        # Jaring pengaman. Keluar normal sudah menutup sesinya sendiri;
        # ini untuk jalur yang TIDAK normal.
        cleanup_orphan_mcp(quiet=True)

    if not result:
        return 1
    evaluation.report(result)
    _save_answer(result)
    return 0


def _save_answer(result) -> None:
    """Simpan jawaban lengkap ke berkas, supaya kegagalan bisa DIDIAGNOSIS.

    Laporan ringkas hanya memberi tahu kasus mana yang meleset, bukan
    KENAPA. Tanpa jawabannya tersimpan, satu-satunya cara memeriksa adalah
    menjalankan ulang kasus itu - dan model tidak deterministik, jadi yang
    Anda periksa belum tentu jawaban yang tadi dinilai.

    Terbukti perlu: kasus aritmetika dinilai gagal, dijalankan ulang justru
    benar. Tanpa berkas ini, mustahil membedakan model yang tidak konsisten
    dari penilai yang keliru.
    """
    import json
    from datetime import datetime

    file = config.ROOT / "evaluation-result.json"
    content = [{
        "tanya": k["tanya"],
        "jenis": k["jenis"],
        "pengguna": k.get("pengguna"),
        "acuan": k["acuan"],
        "jawaban": j,
        "alat_dipanggil": sorted(evaluation.tools_called(p)),
    } for k, p, j in result]
    file.write_text(json.dumps(
        {"waktu": datetime.now().isoformat(timespec="seconds"),
         "model": config.MODEL_CHAT, "storage": config.STORAGE,
         "kasus": content}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Jawaban lengkap tersimpan di {file.name} "
          f"— untuk memeriksa kasus yang meleset.")


async def _satu_kasus(agent, case: dict, seconds_limit: int):
    """Jalankan satu kasus. Kembalikan (pesan, jawaban, detik).

    Kegagalan dibedakan sebabnya, karena perbaikannya berbeda:
    lewat batas waktu = model terlalu lambat; errors = ada yang rusak.
    """
    mulai = time.perf_counter()
    try:
        keluar = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": case["tanya"]}]},
                # Batas langkah: agent yang melingkar berhenti sendiri,
                # bukan menghabiskan seluruh batas waktu.
                {"recursion_limit": STEP_LIMIT},
            ),
            timeout=seconds_limit,
        )
        message = keluar["messages"]
        return message, message[-1].content, time.perf_counter() - mulai
    except TimeoutError:
        # Penanda, BUKAN string kosong. Kasus yang lewat batas dan model yang
        # tidak mengeluarkan apa pun adalah dua kegagalan berbeda dengan
        # tindakan berbeda; sebelum ini keduanya bermuara pada kalimat
        # "model tidak menghasilkan apa pun", yang mengarahkan ke num_ctx.
        print(f"        LEWAT BATAS {seconds_limit}s — dihitung gagal")
        return ([], evaluation.SKIP_LIMIT,
                time.perf_counter() - mulai)
    except Exception as e:
        print(f"        GAGAL: {type(e).__name__}: {e}")
        return ([], f"{evaluation.ERROR_PREFIX} "
                f"{type(e).__name__}]",
                time.perf_counter() - mulai)


def _score(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if wants_help(argv, __doc__):
        return 0

    # Kemajuan harus terlihat MESKI keluaran dialihkan ke berkas.
    #
    # Python memakai buffer blok (bukan per baris) begitu stdout bukan
    # terminal. Untuk perintah biasa itu tak terasa; untuk evaluasi yang
    # memakan 51 menit, akibatnya berkas log DIAM BERMENIT-MENIT lalu tiba-tiba
    # terisi sekaligus. Terjadi saat menyusun lab ini: log berhenti di kasus
    # pertama selama lima belas menit dan terbaca seperti evaluasi yang
    # menggantung, padahal ia berjalan normal.
    #
    # Ini penting justru di tempat evaluasi paling berguna: dijadwalkan,
    # dialihkan ke berkas, atau dijalankan di CI - tepat ketika tidak ada
    # orang yang menunggui layarnya.
    sys.stdout.reconfigure(line_buffering=True)

    limit = _score(argv, "--batas")
    seconds = _score(argv, "--batas-detik")
    again = _score(argv, "--ulang")
    return asyncio.run(run(
        kind=_score(argv, "--jenis"),
        limit=int(limit) if limit else None,
        seconds_limit=int(seconds) if seconds else None,
        again=int(again) if again else 1,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
