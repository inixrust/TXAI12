"""Antarmuka TX-AI12 — dengan login, hak akses, dan penanda mutu ekstraksi.

    streamlit run apps/app12.py

Bedanya dengan pendekatan TX-AI11 ada tiga, dan ketiganya adalah materi
TX-AI12 yang menjadi terlihat:

  1. LOGIN. Peran tidak lagi dipilih dari kotak di sidebar. Identitas datang
     dari login, dan dari identitas itulah sambungan basis data disusun.
     Di TX-AI11 pemilih peran itu dekoratif — `filter_for()` mengabaikannya.

  2. HAK AKSES YANG DITEGAKKAN. Sidebar menunjukkan sebagai siapa sambungan
     dibuka dan apakah RLS sedang berlaku. Ada tombol untuk MEMATIKAN
     filters aplikasi, supaya peserta bisa membuktikan sendiri bahwa yang
     menahan adalah basis data, bukan kode.

  3. PENANDA MUTU EKSTRAKSI + VERIFIKASI SITASI. Sitasi dari halaman
     pindaian diberi tanda; yang belum diverifikasi manusia diberi peringatan.
     Dan tiap sumber bisa dibuka ke HALAMAN ASLINYA dengan bagian yang dibaca
     model disorot — verifikasi terhadap dokumen sumber, bukan chunk indeks.
"""
from __future__ import annotations

import streamlit as st

from .. import audit, config
from ..domain import users as P
from ..generation import NOT_FOUND, answer
from . import citations

TITLE = "Tanya SOP — TX-AI12"


# ---------------------------------------------------- sesi lintas-refresh
#
# st.session_state hilang saat halaman di-refresh - ia terikat pada koneksi
# websocket, bukan browser. Tanpa penanganan, refresh = terlempar ke login.
# Perbaikannya: token DITANDATANGANI (lihat domain/session.py) disimpan di
# cookie; dibaca saat memuat, ditulis ulang saat tampilan utama dirender.
#
# KENAPA DITULIS SAAT RENDER, BUKAN SEBELUM st.rerun(). components.html
# menjalankan JS di iframe; st.rerun() yang dipanggil tepat setelahnya membuang
# delta render itu, jadi JS-nya tak pernah sampai ke browser. Karena itu cookie
# ditulis sebagai bagian render tampilan utama yang normal - bukan di jalur
# login yang langsung rerun.

def _subject_of(person) -> str:
    """Penanda yang ditandatangani ke dalam token: NIP, atau 'PUBLIC' untuk tamu."""
    return "PUBLIC" if person is P.PUBLIC else person.nip


def _cookie_js(value: str, max_age: int) -> str:
    """Perintah menulis cookie ke dokumen INDUK. Iframe komponen ber-srcdoc
    dengan allow-same-origin, jadi window.parent mengenai origin aplikasi -
    terbukti terbaca st.context.cookies setelah refresh."""
    import json
    raw = (f"{config.SESSION_COOKIE}={value}; path=/; "
           f"max-age={max_age}; SameSite=Lax")
    return (f"<script>try{{(window.parent||window).document.cookie="
            f"{json.dumps(raw)};}}catch(e){{}}</script>")


def _write_session_cookie(person) -> None:
    import streamlit.components.v1 as components

    from ..domain import session
    token = session.mint(_subject_of(person))
    components.html(_cookie_js(token, config.SESSION_TTL), height=0)


def _clear_session_cookie() -> None:
    import streamlit.components.v1 as components
    components.html(_cookie_js("", 0), height=0)


def _restore_from_cookie() -> bool:
    """Pulihkan `person` dari cookie sesi yang sah. True bila berhasil.

    Gagal-tertutup: cookie hilang/rusak/kedaluwarsa -> False -> layar login.
    """
    from ..domain import session

    try:
        token = st.context.cookies.get(config.SESSION_COOKIE)
    except Exception:
        return False
    subject = session.verify(token)
    if subject is None:
        return False
    person = P.PUBLIC if subject == "PUBLIC" else P.REGISTRY.get(subject)
    if person is None:                       # NIP tak dikenal lagi (mis. dicabut)
        return False
    st.session_state.person = person
    st.session_state.setdefault("history", [])
    return True


# ------------------------------------------------------------------ login

def _new_session_id() -> str:
    """Satu id per sesi web. Dibuat SAAT identitas ditetapkan (login/tamu),
    bukan menunggu render utama - supaya event audit login pun sudah membawa
    session_id, dan seluruh aktivitas satu sesi berdampingan di Langfuse."""
    import uuid
    return f"web-{uuid.uuid4().hex[:12]}"


def _login_screen() -> None:
    st.title(TITLE)
    st.caption("Masuk lebih dulu. Hak akses ditentukan unit dan peran Anda.")

    with st.form("masuk"):
        option = P.demo_users()
        label = [f"{o.nip} — {o.name} ({o.unit}, {o.role})" for o in option]
        idx = st.selectbox("Pengguna", range(len(option)),
                           format_func=lambda i: label[i])
        password = st.text_input("Kata sandi", type="password",
                              help="Kata sandi lab: lab2026")
        if st.form_submit_button("Masuk"):
            person = P.login(option[idx].nip, password)
            if person is None:
                # Audit: NIP yang DICOBA dicatat (deteksi percobaan paksa),
                # sandinya TIDAK - tidak pernah menyentuh audit.record.
                audit.record("login-gagal", subject=option[idx].nip,
                             outcome="ditolak")
                st.error("NIP atau kata sandi salah.")
            else:
                st.session_state.person = person
                st.session_state.history = []
                st.session_state.pop("_suppress_restore", None)
                st.session_state.id_sesi = _new_session_id()
                audit.record("login", person, outcome="berhasil",
                             session=st.session_state.id_sesi)
                st.rerun()

    # Tier tanpa login. Kuncinya: PUBLIC, BUKAN None. PUBLIC memberi sambungan
    # non-pemilik yang RLS-nya hanya meloloskan klasifikasi 'umum'; None justru
    # membuka SEMUA dokumen lewat sambungan pemilik yang kebal RLS. Lihat
    # users._Public. Tombol di LUAR form karena form hanya punya satu submit.
    if st.button("Lanjut sebagai tamu (hanya dokumen umum)"):
        st.session_state.person = P.PUBLIC
        st.session_state.history = []
        st.session_state.pop("_suppress_restore", None)
        st.session_state.id_sesi = _new_session_id()
        audit.record("tamu-masuk", P.PUBLIC, outcome="berhasil",
                     session=st.session_state.id_sesi)
        st.rerun()

    st.info(
        "Pengguna di daftar ini adalah orang yang sama dengan isi tabel "
        "`karyawan` di basis data Oracle — supaya lab Hari 3 nyambung."
    )


# ---------------------------------------------------------------- sidebar

def _sidebar() -> tuple[int, bool, bool]:
    person = st.session_state.person
    guest = person is P.PUBLIC

    with st.sidebar:
        if guest:
            # _Public tak punya .name/.role — jangan membacanya.
            st.subheader("Tamu")
            st.caption("publik · hanya dokumen umum")
        else:
            st.subheader(person.name)
            st.caption(f"{person.unit} · {person.role}")
        # Bagi tamu, tombol ini bermakna "masuk" (kembali ke layar login);
        # mekanismenya sama - hapus identitas lalu render ulang.
        if st.button("Masuk" if guest else "Keluar"):
            audit.record("keluar", person,
                         session=st.session_state.get("id_sesi"))
            del st.session_state.person
            st.session_state.pop("id_sesi", None)
            # Tandai supaya run() TIDAK memulihkan lagi dari cookie pada rerun
            # ini, dan menghapus cookie-nya di layar login (di sanalah JS-nya
            # sempat berjalan - lihat catatan di atas _write_session_cookie).
            st.session_state._suppress_restore = True
            st.rerun()

        st.divider()
        st.markdown("**Hak akses**")

        pgvector = config.STORAGE.strip().lower() == "pgvector"
        if pgvector:
            # Tamu tersambung sebagai rag_app TANPA unit: GUC tak disetel,
            # current_setting(...) NULL, RLS hanya meloloskan 'umum'.
            unit_txt = ("— (tanpa unit, umum saja)" if guest
                        else f"`{person.unit}`")
            st.success(f"Tersambung sebagai `rag_app`\n\n"
                       f"`{config.GUC_UNIT}` = {unit_txt}")
            st.caption("RLS berlaku pada setiap query, termasuk yang lupa "
                       "menyaring.")
        else:
            st.warning(
                "Penyimpanan `chroma` — TIDAK mengenal hak akses per users. "
                "Pembatasan hanya bergantung pada filters di aplikasi."
            )

        # Sakelar yang membuat pelajarannya bisa dibuktikan, bukan dipercaya.
        # Hanya untuk user login: ia memperagakan RLS dengan mematikan lapis
        # aplikasi. Tamu tak punya lapis unit untuk diperagakan dan selalu
        # tersaring ke 'umum', jadi sakelarnya tak ditampilkan.
        if guest:
            filters_active = True
        else:
            filters_active = st.checkbox(
                "Penyaring aplikasi aktif", value=True,
                help="Matikan untuk membuktikan bahwa yang menahan adalah basis "
                     "data, bukan kode aplikasi. Pada pgvector hasilnya tetap "
                     "tersaring; pada chroma semuanya bocor.")
            if not filters_active and not pgvector:
                st.error("Penyaring mati + Chroma = dokumen terbatas akan bocor. "
                         "Itulah yang sedang diperagakan.")

        st.divider()
        k = st.slider("Jumlah chunks diambil", 2, 8, config.N_FINAL)
        source_show = st.checkbox("Tampilkan sumber", value=True)

        st.divider()
        st.caption(
            f"Penyimpanan: `{config.STORAGE}` · Model: `{config.MODEL_CHAT}`\n\n"
            f"Embedding: `{config.MODEL_EMBEDDING}` · Vision: `{config.MODEL_VISION}`"
        )
        st.caption("Seluruh proses berjalan di mesin ini. Tidak ada dokumen "
                   "yang dikirim ke luar organisasi.")

    return k, source_show, filters_active


# ----------------------------------------------------------------- sumber

def _show_source(chunks) -> None:
    """Daftar sumber, dengan penanda asal dan mutu ekstraksi.

    Inilah yang tidak ada di TX-AI11: pembaca diberi tahu bahwa sebuah
    kutipan berasal dari pembacaan MESIN atas halaman pindaian, dan apakah
    pembacaan itu sudah diperiksa manusia. Menyembunyikannya berarti
    menyamakan kutipan dari PDF ber-lapisan teks dengan kutipan dari
    fotokopi buram — dan keduanya tidak sama layak dipercaya.
    """
    if not chunks:
        return

    st.markdown("**Sumber**")
    for i, d in enumerate(chunks, 1):
        m = d.metadata
        title = f"[{i}] {m.get('source', '?')}"
        if m.get("page") is not None:
            title += f" — hal. {m['page'] + 1}"

        marker = []
        if m.get("ekstraksi") == "vlm":
            marker.append(f"hasil pindaian, dibaca `{m.get('model_ekstraksi', 'VLM')}`")
        if m.get("klasifikasi") == "terbatas":
            marker.append(f"terbatas · {m.get('unit', '?')}")

        with st.expander(title + ("  ·  " + " · ".join(marker) if marker else "")):
            if m.get("mutu_ekstraksi") == "perlu_tinjau":
                st.warning(
                    "Halaman ini ditandai **perlu ditinjau manusia**. "
                    "Angka di dalamnya berasal dari pembacaan otomatis dan "
                    "belum diverifikasi — periksa dokumen aslinya sebelum "
                    "menindaklanjuti hal yang berkonsekuensi."
                )
            elif m.get("ekstraksi") == "vlm":
                st.info(
                    "Hasil pembacaan otomatis halaman pindaian. Lolos "
                    "pemeriksaan struktural, tetapi bukan jaminan benar."
                )

            _verify_source(d)


def _verify_source(d) -> None:
    """Tampilkan sumber ASLI untuk memeriksa sitasi — dibaca ulang dari
    dokumen sumber, BUKAN dari chunk di indeks.

    Dua jenis dokumen, dua cara verifikasi yang jujur:

      pindaian -> GAMBAR halaman yang PERSIS dibaca model (VLM). Tidak ada
                  teks asli untuk diperiksa; yang model lihat adalah gambar,
                  jadi itu yang ditampilkan - pengguna menilai sendiri apakah
                  angka yang dikutip memang ada di halaman itu.
      teks     -> halaman asli dengan bagian yang dibaca model DISOROT. Kalau
                  chunk-nya salah halaman atau terpotong keliru, cuplikan
                  indeks ikut salah tanpa ketahuan; halaman asli menangkapnya.

    Hanya teks/gambar HALAMAN yang dikirim, tidak pernah berkasnya - memeriksa
    sitasi bukan mengunduh dokumen. Aman RLS: chunks di sini SUDAH tersaring
    hak akses users saat retrieval, jadi hanya halaman yang boleh ia lihat.
    """
    m = d.metadata
    quote = citations.original_content(d)

    if m.get("ekstraksi") == "vlm":
        image = citations.scanned_page(m)
        if image is not None:
            st.caption("Halaman PINDAIAN yang dibaca model — periksa bacaannya:")
            st.image(image, use_container_width=True)
            st.caption("Teks yang model baca dari halaman ini:")
            st.text(quote[:1200])
        else:
            st.caption("Pindaian tak ditemukan; yang dibaca model:")
            st.text(quote[:1200])
        return

    text, remark = citations.original_page(m)
    if text is None:
        st.caption("Dokumen asli tak terbaca; yang dibaca model:")
        st.text(quote[:1200])
        if remark:
            st.caption(remark)
    else:
        st.caption(f"{remark} — bagian bersorot inilah yang dibaca model.")
        st.html(citations.highlight_html(text, quote))


# ---------------------------------------------------------------- jawaban

def _answer(query_text: str, k: int, source_show: bool, filters_active: bool) -> None:
    person: P.User = st.session_state.person

    with st.chat_message("assistant"):
        try:
            with st.spinner("Mencari di dokumen..."):
                # Mematikan filters aplikasi TIDAK ikut mematikan
                # identitas basis data: `orang=` tetap terkirim. Itulah yang
                # membuat peragaannya bermakna — kalau keduanya dimatikan,
                # sambungan kembali ke pemilik tabel yang kebal RLS dan yang
                # terbukti bukan apa-apa.
                content, chunks, _ = answer(
                    query_text,
                    app_user=person if filters_active else None,
                    person=person,
                    session=st.session_state.id_sesi,
                    k=k, show_chunks=False,
                )
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Gagal memproses: {type(e).__name__}. "
                     f"Periksa Ollama dan container Postgres, lalu coba lagi.")
            st.stop()

        # PENJAGA KELUARAN (OWASP LLM07). Diterapkan tepat sebelum
        # ditampilkan, bukan di dalam jawab(): yang perlu dijaga adalah apa
        # yang SAMPAI ke users, dan jalur ini satu-satunya yang menampilkan.
        from ..domain.guard import screen as saring_keluaran

        content = saring_keluaran(content)
        st.markdown(content)

        if NOT_FOUND in content:
            st.info("Sistem menolak menjawab — itu perilaku yang benar bila "
                    "informasinya memang tidak ada di dokumen yang boleh "
                    "Anda akses.")

        not_yet = sum(d.metadata.get("mutu_ekstraksi") == "perlu_tinjau"
                    for d in chunks)
        if not_yet:
            st.warning(f"{not_yet} dari {len(chunks)} sumber berasal dari "
                       f"halaman pindaian yang belum diverifikasi manusia.")

        if source_show:
            _show_source(chunks)

    # Audit: FAKTA pertanyaan (siapa, ditolak/dijawab, berapa sumber) - BUKAN
    # teks pertanyaannya. Jejak LLM 'jawab-sop' sudah memuat isinya bila
    # diagnosis mendalam diperlukan; audit cukup mencatat peristiwanya.
    audit.record("tanya", person, session=st.session_state.get("id_sesi"),
                 outcome="ditolak" if NOT_FOUND in content else "dijawab",
                 jumlah=len(chunks))

    st.session_state.history.append(
        {"peran": "assistant", "isi": content, "potongan": chunks})


# ------------------------------------------------------ alur LangGraph (L10)

def _run_flow(inputs, thread_id: str):
    """Jalankan/lanjutkan graf pada thread_id, kembalikan state akhir.

    Checkpointer dibuka BARU tiap aksi, bukan disimpan di memori proses: itu
    justru yang membuktikan keadaan benar-benar ada di Postgres. Aksi apa pun -
    pertanyaan baru atau melanjutkan setelah tinjauan - memakai thread_id yang
    sama dan memungut keadaannya dari basis data. Inilah pemulihan-setelah-mati
    L10, diperagakan lewat UI.
    """
    from ..flow import build_graph, open_checkpointer

    with open_checkpointer() as cp:
        cp.setup()
        graph = build_graph(checkpointer=cp)
        return graph.invoke(inputs, config={"configurable":
                                             {"thread_id": thread_id}})


def _flow_result() -> None:
    hasil = st.session_state.get("alur_hasil")
    if not hasil:
        return
    st.divider()
    label = {"approved": "disetujui peninjau", "rejected": "ditolak peninjau",
             "revised": "diminta revisi", "lolos": "lolos otomatis"}.get(
                 hasil.get("status"), hasil.get("status") or "selesai")
    st.markdown(f"**Hasil akhir — _{label}_:**")
    st.markdown(hasil.get("answer_text") or "—")
    if hasil.get("note"):
        st.caption(f"Catatan peninjau: {hasil['note']}")
    if st.button("Mulai percakapan baru"):
        for k in ("alur_thread", "alur_tunda", "alur_hasil"):
            st.session_state.pop(k, None)
        st.rerun()


def _flow_panel(person) -> None:
    """Alur LangGraph berkeadaan (L10) dengan tinjauan manusia — di UI.

    Beda dari tab 'Tanya' (jalur answer() sederhana): tiap percakapan di sini
    punya thread_id, keadaannya tersimpan di Postgres, dan jawaban BERISIKO
    berhenti menunggu persetujuan sebelum dikirim. Karena keadaan ada di basis
    data, alur ini pulih meski proses mati di tengah - itulah inti L10, kini
    bisa dilihat dan dijalankan, bukan sekadar lulus di test.

    Retrieval di dalam graf memakai identitas pemohon (NIP) untuk RLS - lihat
    n_search_documents; tanpa itu graf mengambil sebagai pemilik yang kebal RLS.
    """
    import uuid

    from langgraph.types import Command

    st.subheader("Konsultasi kebijakan")
    st.caption(
        "Pertanyaan **fakta** dijawab langsung. Pertanyaan **penilaian / "
        "kepatuhan** — jawaban yang memvonis _boleh/tidak/melanggar_ atas "
        "situasi Anda — **ditahan untuk disetujui peninjau** sebelum dirilis. "
        "Begitu juga jawaban yang sumbernya lemah atau belum diverifikasi.")

    tunda = st.session_state.get("alur_tunda")

    # --- Tidak ada tinjauan tertunda: form pertanyaan ---
    if tunda is None:
        with st.form("alur_tanya"):
            q = st.text_input(
                "Pertanyaan",
                placeholder="mis. Apakah saya boleh mengambil cuti tahunan "
                            "20 hari sekaligus?")
            if st.form_submit_button("Kirim") and q.strip():
                tid = f"alur-{uuid.uuid4().hex[:12]}"
                st.session_state.alur_thread = tid
                st.session_state.pop("alur_hasil", None)
                with st.spinner("Memproses pertanyaan Anda..."):
                    # Tanpa sakelar paksa: alur ditentukan aturan nyata
                    # (penilaian/cakupan/sumber), bukan pilihan di UI.
                    res = _run_flow(
                        {"question": q, "nip": getattr(person, "nip", "")}, tid)
                itr = res.get("__interrupt__")
                if itr:
                    st.session_state.alur_tunda = dict(itr[0].value)
                else:
                    st.session_state.alur_hasil = {
                        "answer_text": res.get("answer_text"),
                        "status": res.get("status") or "lolos"}
                st.rerun()
        st.caption(
            "Contoh **dijawab langsung**: _Berapa lama masa percobaan pegawai "
            "baru?_ — Contoh **butuh persetujuan**: _Apakah saya boleh "
            "mengambil cuti tahunan 20 hari sekaligus?_")
        _flow_result()
        return

    # --- Ada tinjauan tertunda: kartu keputusan ---
    st.warning("⏸ Jawaban ditahan untuk ditinjau sebelum dikirim ke pemohon.")
    st.markdown(f"**Pertanyaan:** {tunda.get('question')}")
    st.markdown(f"**Jawaban usulan:**\n\n{tunda.get('answer_text')}")
    st.caption(f"Alasan ditahan: _{tunda.get('hold_reason')}_ · cakupan sitasi "
               f"{tunda.get('citation_coverage', 0):.0%}")
    sumber = list(dict.fromkeys(s for s in (tunda.get("source") or []) if s))
    if sumber:
        st.caption("Sumber: " + ", ".join(sumber))

    catatan = st.text_input("Catatan untuk revisi (opsional)", key="alur_catatan")
    kolom = st.columns(3)
    keputusan = None
    if kolom[0].button("✓ Setujui", type="primary"):
        keputusan = {"action": "approve"}
    if kolom[1].button("✗ Tolak"):
        keputusan = {"action": "reject"}
    if kolom[2].button("↻ Minta revisi"):
        keputusan = {"action": "revise", "note": catatan}

    if keputusan is not None:
        with st.spinner("Menerapkan keputusan peninjau..."):
            res = _run_flow(Command(resume=keputusan),
                            st.session_state.alur_thread)
        st.session_state.alur_hasil = {
            "answer_text": res.get("answer_text"),
            "status": res.get("status"), "note": res.get("note")}
        st.session_state.pop("alur_tunda", None)
        audit.record("tinjau-alur", person, outcome=keputusan["action"],
                     session=st.session_state.get("id_sesi"))
        st.rerun()

    _flow_result()


# ------------------------------------------------------------------ utama

BADGE = {"menunggu": ":gray[menunggu]", "diproses": ":blue[diproses]",
           "selesai": ":green[selesai]", "gagal": ":red[GAGAL]"}


def _upload_panel(person) -> None:
    """Unggah dokumen ke queue ingest, lalu tampilkan statusnya.

    KENAPA UNGGAHNYA TIDAK MENGINDEKS DI SINI.

    Godaan terbesar pada ui adalah memproses langsung di dalam
    penanganan tombol: berkas masuk, ekstraksi jalan, indeks bertambah, satu
    fungsi saja. Itu bekerja di lab dengan satu dokumen kecil, dan runtuh di
    tempat lain: ekstraksi VLM satu halaman memakan sekitar dua menit di
    mesin ini, dan selama itu Streamlit menahan seluruh sesi. Pengguna
    melihat halaman menggantung tanpa tahu apakah berkasnya sudah aman.

    Yang dilakukan di sini hanya dua langkah cepat - SIMPAN berkasnya, lalu
    TARUH tugas di queue - dan keduanya selesai dalam sepersekian detik.
    Pekerja terpisah yang mengerjakan sisanya. Pemisahan itulah keseluruhan
    pelajaran modul ini.
    """
    from ..ingest import blob, queue

    st.subheader("Unggah dokumen")
    st.caption("Berkas disimpan dan dimasukkan ke queue. Pengindeksan "
               "dikerjakan pekerja di latar — halaman ini tidak menunggu.")

    file = st.file_uploader("Pilih berkas", type=["pdf", "md", "txt"])
    column = st.columns(2)
    kind = column[0].selectbox("Jenis dokumen", ("sop", "edaran", "notulen"))
    # Klasifikasi bawaannya `terbatas`, dan urutan pilihannya pun begitu:
    # pilihan pertama adalah pilihan yang paling sering tidak diubah orang.
    classification = column[1].selectbox("Klasifikasi", ("terbatas", "umum"))

    if file is not None and st.button("Masukkan ke queue", type="primary"):
        from ragcore.application import build_ingest_service
        from ragcore.ingest import blob

        # Unit tidak dikirim ke service: IngestService mengambilnya dari
        # `uploader` (person) - itulah yang mencegah 'tandai dokumenku milik
        # unit lain'. Adapter ini hanya meneruskan identitas dan pilihan form.
        sesi = st.session_state.get("id_sesi")
        try:
            receipt = build_ingest_service().submit(
                file.name, file.getvalue(), uploader=person,
                kind=kind, classification=classification)
        except blob.TooLarge as e:
            audit.record("unggah-ditolak", person, outcome="ditolak",
                         berkas=file.name, alasan=str(e), session=sesi)
            st.error(f"Berkas ditolak: {e}")
            return
        audit.record("unggah", person, outcome="antre", berkas=receipt.name,
                     jenis=kind, klasifikasi=receipt.classification,
                     session=sesi)
        # Lacak id unggahan SESI ini di session_state (ephemeral). Inilah yang
        # membuat daftar di bawah tidak menetap permanen: begitu halaman dimuat
        # ulang, session_state bersih dan unggahan yang sudah 'selesai' hilang
        # dari layar - user toh sudah melihatnya selesai.
        st.session_state.setdefault("unggahan", []).append(receipt.task_id)
        st.success(f"[{receipt.task_id}] {receipt.name} masuk antrean "
                   f"(unit {receipt.unit}, {receipt.classification}).")
        st.caption("Diproses otomatis di latar. Tekan **Segarkan** untuk "
                   "melihat statusnya berubah menjadi *selesai*.")

    # Yang MASIH berjalan milik user (bertahan lintas-refresh) + yang diunggah
    # SESI ini (agar transisi ke 'selesai' terlihat sekali). 'Selesai' dari
    # sesi lama tidak ikut - tak disimpan permanen di layar. Lihat for_panel().
    task = queue.for_panel(getattr(person, "nip", None),
                           st.session_state.get("unggahan"))
    st.subheader("Unggahan Anda")
    if st.button("Segarkan"):
        st.rerun()
    if not task:
        st.caption("Tidak ada unggahan yang sedang diproses.")
        return
    for t in task:
        badge = BADGE.get(t["status"], t["status"])
        row = f"{badge} · **{t['nama_berkas']}**"
        if t["potongan"]:
            row += f" · {t['potongan']} potongan"
        st.markdown(row)
        if t["pesan"]:
            # Sebab kegagalan ditampilkan ke PENGUNGGAH, bukan hanya ke log
            # pekerja. Orang yang mengunggah tidak membaca log; yang harus
            # terbaca olehnya adalah "kenapa dokumen saya tidak masuk".
            st.caption(f"↳ {t['pesan']}")


def run() -> None:
    st.set_page_config(page_title=TITLE, page_icon=":lock:", layout="centered")

    # Titipkan satu pekerja ingest ke proses aplikasi ini, supaya dokumen yang
    # diunggah diproses di latar SAMPAI SELESAI tanpa terminal pekerja terpisah.
    # Idempoten dan memulihkan diri: dipanggil tiap rerun, tapi hanya
    # menghidupkan bila belum ada thread yang hidup. Peragaan dua-pekerja tetap
    # bisa - jalankan `python -m ragcore.commands.worker` di samping; keduanya
    # berbagi queue lewat FOR UPDATE SKIP LOCKED.
    from ..ingest.worker import ensure_background_worker
    ensure_background_worker()

    if "person" not in st.session_state:
        # Pulihkan sesi dari cookie bertanda-tangan supaya refresh tidak
        # mengeluarkan user. Dilewati setelah logout (_suppress_restore).
        #
        # KENAPA _suppress_restore TIDAK di-pop di sini. st.context.cookies
        # dibaca sekali saat koneksi websocket dibuka dan TIDAK menyegar pada
        # rerun berikutnya - jadi setelah logout, penghapusan cookie lewat JS
        # belum "terlihat" server sampai halaman benar-benar dimuat ulang.
        # Kalau flag ini dilepas pada render pertama, interaksi berikutnya di
        # layar login (memilih user lain) akan memulihkan user LAMA dari cookie
        # yang masih terbaca. Maka flag dipertahankan sepanjang sesi ini;
        # hanya login/tamu sungguhan yang melepasnya. Refresh penuh memulai
        # sesi baru tanpa flag - dan cookie memang sudah terhapus di browser.
        suppress = st.session_state.get("_suppress_restore", False)
        restored = (not suppress) and _restore_from_cookie()
        if not restored:
            if suppress:
                _clear_session_cookie()
            _login_screen()
            return

    st.session_state.setdefault("history", [])
    # Tulis/segarkan cookie sesi saat tampilan utama dirender (BUKAN sebelum
    # rerun - JS-nya tak akan sempat jalan). Ini juga memperpanjang masa berlaku
    # tiap interaksi: sliding expiration.
    _write_session_cookie(st.session_state.person)
    # Satu id per percakapan, dibuat sekali saat sesi dimulai. Inilah yang
    # membuat seluruh giliran tampil berdampingan di Langfuse — pertanyaan
    # lanjutan yang meleset hampir selalu masuk akal begitu giliran
    # sebelumnya ikut terlihat.
    # Sesi login/tamu sudah menetapkan id_sesi lebih dulu (supaya event audit
    # login ikut membawanya). Yang sampai ke sini tanpa id_sesi adalah sesi
    # yang DIPULIHKAN dari cookie - ia dapat id barunya di sini.
    if "id_sesi" not in st.session_state:
        st.session_state.id_sesi = _new_session_id()

    k, source_show, filters_active = _sidebar()

    st.title(TITLE)
    st.caption("Menjawab hanya dari dokumen yang masih berlaku DAN yang "
               "boleh Anda akses.")

    # Tamu: baca-saja, satu tab. Tab unggah tak ditampilkan - menulis wajib
    # login (IngestService.submit menolak PUBLIC, ini menyembunyikannya lebih
    # dulu supaya tak ada tombol yang pasti gagal).
    if st.session_state.person is P.PUBLIC:
        st.info("Anda menjelajah sebagai tamu — hanya dokumen berklasifikasi "
                "umum. Masuk untuk akses sesuai unit Anda.")
        _question_panel(k, source_show, filters_active)
        return

    question_tab, tab_alur, tab_upload = st.tabs(
        ["Tanya", "Konsultasi", "Unggah dokumen"])
    with tab_upload:
        _upload_panel(st.session_state.person)

    with tab_alur:
        _flow_panel(st.session_state.person)

    with question_tab:
        _question_panel(k, source_show, filters_active)


def _question_panel(k: int, source_show: bool, filters_active: bool) -> None:
    """Percakapan tanya-jawab, dipisah agar muat di dalam tab."""
    for message in st.session_state.history:
        with st.chat_message(message["peran"]):
            st.markdown(message["isi"])
            if message.get("potongan") and source_show:
                _show_source(message["potongan"])

    query_text = st.chat_input("Contoh: Apa aturan kata sandi sistem internal?")
    if not query_text:
        return

    st.session_state.history.append({"peran": "user", "isi": query_text})
    with st.chat_message("user"):
        st.markdown(query_text)

    _answer(query_text, k, source_show, filters_active)
