# Runbook — sistem RAG dokumen + basis data

Untuk orang yang **tidak ikut membangun** sistem ini. Setiap gejala punya
langkah berurutan; berhenti di langkah pertama yang gagal.

---

## Gejala: semua pertanyaan dijawab "tidak ditemukan"

1. **Indeksnya masih ada?**
   ```bash
   psql -h localhost -p 6024 -U rag -d korpus -c "SELECT COUNT(*) FROM potongan_ncs;"
   ```
   Diharapkan > 400. Kalau 0 → lompat ke "Membangun ulang indeks".

2. **Model embedding sama dengan saat indeks dibangun?**
   ```bash
   ollama list | grep bge-m3
   ```
   Kalau model lain → lompat ke "Model tertukar". Ini penyebab paling sering
   dan paling senyap: tidak ada galat, skor tetap keluar, hasilnya acak.

3. **Ollama menjalankannya di GPU?**
   ```bash
   ollama ps
   ```
   Kolom PROCESSOR menunjukkan CPU → sistem berjalan tapi sangat lambat.
   Bukan penyebab "tidak ditemukan". Lanjut ke langkah 4.

4. **Pencarian mengembalikan sesuatu?**
   ```bash
   python -m rag_lab12.perintah.cari "masa percobaan"
   ```
   Kosong padahal langkah 1-2 lolos → penyaring metadata terlalu ketat.
   Periksa nilai `app.unit_pengguna` pada sesi (lihat gejala RLS di bawah).

---

## Gejala: satu unit tidak melihat apa pun, unit lain normal

Hampir selalu Row-Level Security.

1. Periksa nilai yang disetel aplikasi:
   ```sql
   SELECT current_setting('app.unit_pengguna', true);
   ```
   NULL → sesi tidak menyetelnya. Seluruh dokumen berklasifikasi terbatas
   akan tersaring, dan itu benar — perbaikannya di sisi login, bukan di RLS.

2. Nilai unit harus **persis** sama dengan kolom `unit`:
   ```sql
   SELECT DISTINCT unit FROM potongan_ncs ORDER BY 1;
   ```
   "Divisi TI" tidak sama dengan "divisi ti".

3. Kalau SEMUA unit melihat SEMUA baris, sambungannya memakai **pemilik
   tabel** — pemilik kebal RLS. Sambungkan sebagai `rag_app`.

---

## Gejala: jawaban memuat angka yang salah

1. Apakah sumbernya hasil VLM yang belum diverifikasi?
   ```sql
   SELECT langchain_metadata->>'source', langchain_metadata->>'mutu_ekstraksi'
   FROM potongan_ncs WHERE langchain_metadata->>'ekstraksi' = 'vlm';
   ```
2. Kalau `perlu_tinjau`, buka halaman aslinya di `dokumen_pindaian/` dan
   bandingkan. Ini bukan kerusakan sistem — ini yang memang harus dikerjakan
   manusia, dan penandanya sudah menunjukkan di mana.
3. Setelah diperiksa, ubah penandanya menjadi `terverifikasi`.

---

## Gejala: proses pengindeksan mati di tengah

Alur LangGraph memakai checkpointer Postgres. Jalankan ulang dengan
`thread_id` **yang sama** — ia melanjutkan dari simpul terakhir yang selesai,
bukan dari awal.

```python
konfig = {"configurable": {"thread_id": "pengindeksan-arsip-2019"}}
alur.invoke(None, konfig)              # None = lanjutkan
print(alur.get_state(konfig).next)     # sampai mana ia berjalan
```

---

## Membangun ulang indeks

Butuh sekitar `<isi dari lembar kapasitas>` jam untuk arsip penuh.

```bash
docker compose -f compose-pgvector.yaml up -d
PENYIMPANAN=pgvector python -m rag_lab12.perintah.indeks --ulang
python -m rag_lab12.perintah.rls --pasang
```

Ekstraksi VLM **tidak** diulang selama berkas `*.vlm.txt` masih ada.
Jangan menghapusnya untuk "membersihkan".

---

## Model tertukar

Tidak ada keadaan setengah jalan yang benar. Indeks yang separuhnya dibangun
dengan model embedding berbeda memberi peringkat yang tampak wajar tetapi
salah, tanpa satu pun galat.

1. Kembalikan `MODEL_EMBEDDING` ke `bge-m3`, atau
2. Bangun ulang **seluruh** indeks dengan model yang baru — bukan sebagian.

Kalau dimensi model barunya bukan 1024, `DIMENSI_EMBEDDING` ikut berubah dan
tabelnya harus dibuat ulang, bukan diisi ulang.
