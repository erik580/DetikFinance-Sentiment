# Roadmap — Text Mining Pipeline (Sentimen Berbasis Topik, DetikFinance)

**Scope:** berhenti di text mining. Output akhir = **agregat berita × bank × aspek**
(`score`, `count`, metadata hilir), sebagai data pendukung eksternal untuk model prediksi
*abnormal return* (model prediktif **di luar** scope repo ini).

Setiap fase punya **satu notebook** + modul `src/` yang bisa dipakai ulang, plus **kriteria selesai**
dan **risiko yang mungkin bikin masalah** (sesuai permintaanmu agar tahu di mana bisa macet).

---

## Peta aliran

```
Fase 0  Pilot crawler ....................... verifikasi HTML, volume, disk        [SELESAI]
Fase 1  Crawl indeks (L0) ................... simpan link + metadata semua artikel
Fase 2  Scrape artikel (L2) ................. unduh HTML lengkap (gz) → parse teks
Fase 3  Cleaning + dedup ................... boilerplate, filter, near-duplicate
Fase 4  Tiering relevansi .................. skor per bank → Tier A/B/C/D
Fase 5  Segmentasi + entity linking ........ kalimat × bank
Fase 6  BERTopic (≤ 31 Des 2024) ........... topik → taksonomi aspek A1–A8/S1–S3
Fase 7  Anotasi gold (+ silver LLM opsional)  label manual 300±; LLM sebagai bantuan
Fase 8  ABSA IndoBERT ..................... fine-tune → klasifikasi aspek+sentimen sisa data
Fase 9  Agregasi final .................... berita × bank × aspek (score, count)
```

---

## Fase 0 — Pilot Crawler ✅ (sudah dikerjakan)

**Notebook:** `00_pilot_crawl.ipynb` · **Modul:** `src/crawl.py`, `src/parse.py`

**Hasil verifikasi:**
- URL indeks `?page={n}&date=MM/DD/YYYY` jalan **server-side** (tak perlu Playwright/JS).
- Selektor **stabil di 3 era** (2022/2024/2026): `h1.detail__title`, `.detail__body-text`,
  `meta[name=publishdate]` (presisi detik, WIB).
- ~20 artikel/halaman; hari normal ~6 halaman (~110 artikel).
- Disk gz: ~48 KB/artikel, ~25 KB/indeks → **proyeksi skenario C ≈ 1.6 GB**.
- robots.txt: `*` → `Allow: /`; larangan `?date=`/`indeks` hanya untuk Googlebot (lihat catatan etika).

**Risiko:** template bisa berubah untuk tahun yang belum diuji → selektor di `config.yaml` dibuat
agar mudah ditambal per era.

---

## Fase 1 — Crawl indeks (L0)

**Notebook:** `01_crawl_index.ipynb` · **Modul:** `src/crawl.py` (sudah ada), `src/pipeline_index.py` (baru)

Iterasi semua tanggal `2024-01-02 → 2026-09-30` (Opsi A), semua halaman, simpan HTML indeks (gz) +
tabel `news_raw` (url, article_id, title, subchannel, date_text). Checkpoint per tanggal agar
bisa dilanjutkan.

**Selesai bila:** `news_raw` lengkap untuk seluruh rentang; grafik artikel/hari tanpa "lubang"
tak wajar; gagal-fetch tercatat & bisa diulang.

**Risiko:** (a) rate-limit/429 pada crawl panjang → sudah ada backoff; (b) hari arsip kosong di
tahun lama → turunkan ke opsi B/A sesuai aturan jatuh-mundur; (c) durasi ~2.5–5 jam.

---

## Fase 2 — Scrape artikel (L2) + parse

**Notebook:** `02_scrape_articles.ipynb` · **Modul:** `src/parse.py` (sudah ada)

Terapkan **seleksi kandidat L1** (judul/subchannel memuat alias bank / kata kebijakan /
sub-kanal bursa / IHSG-rupiah-inflasi) + sampel acak 2% non-kandidat (kontrol negatif).
Unduh HTML artikel kandidat (gz) → parse ke `news_clean` awal (body_text, n_words, published_at).

**Selesai bila:** semua kandidat punya HTML tersimpan + teks terparse; gagal parse ≤ 2% per era.

**Risiko:** (a) artikel multi-halaman → sudah ditangani via `?single=1`; (b) subchannel foto/video
→ difilter; (c) perubahan selektor per era → uji 2022/23/24/25/26.

---

## Fase 3 — Cleaning + deduplikasi

**Notebook:** `03_clean_dedup.ipynb` · **Modul:** `src/clean.py` (baru)

NFKC, buang boilerplate ("Baca juga", "Simak Video", caption, inisial reporter, dateline
"Jakarta -"), filter < 40 kata & advertorial, dedup eksak (hash judul+teks) + near-duplicate
(MinHash LSH, Jaccard ≥ 0.8, jendela ±2 hari).

**Selesai bila:** `news_clean` final; statistik dibuang-per-alasan & rasio duplikat/bulan tercatat.

**Risiko:** boilerplate khas Detik berubah antar-era → pola di file terpisah yang bisa diperluas.

---

## Fase 4 — Tiering relevansi per bank

**Notebook:** `04_tiering_relevance.ipynb` · **Modul:** `src/tiering.py` (baru)

Skor `s_b = 3·[judul] + 2·[3 kalimat awal] + min(badan,3)`; Tier A (≥3) / B (grup/regulasi) /
C (pasar-makro) / D (buang). Ini realisasi "pembobotan" yang kamu maksud: Tier A bobot penuh,
grup bobot 0.5, Tier C hanya konteks. **Berita makro/pasar tetap masuk** (dibutuhkan BERTopic).

**Selesai bila:** `tier` per (artikel, bank) terisi; **presisi Tier A ≥ 90%** (cek manual 100).

**Risiko:** "Mandiri" ambigu (induk vs Mandiri Sekuritas) → aturan subsidiary; alias kurang
lengkap → perluas dari temuan pilot.

---

## Fase 5 — Segmentasi kalimat + entity linking

**Notebook:** `05_segment_link.ipynb` · **Modul:** `src/segment.py`, `src/link.py` (baru)

Segmentasi kalimat (regex + daftar singkatan Indonesia terlindungi). Linking per bank:
`explicit` (alias) / `inherited` (anaforik di artikel 1-bank) / `group` (bobot 0.5).
Kalimat 2 bank → 2 baris. Output `sentences` + `sentence_bank` (belum berlabel).

**Selesai bila:** error segmentasi ≤ 3% (uji 200 kalimat); presisi tautan ≥ 95% (audit 200).

**Risiko:** singkatan tak terduga memecah kalimat; anafora ambigu di artikel multi-bank → dibuang.

---

## Fase 6 — BERTopic → taksonomi aspek

**Notebook:** `06_bertopic.ipynb` · **Modul:** `src/topics.py` (baru)

**Latih BERTopic hanya pada kalimat Tier A/B dengan `published_at ≤ 2024-12-31`** (anti-mengintip;
Opsi A: train ≤ 2024, validasi = 2025, hold-out = 2026).
Embedding `multilingual-e5-base`; sapu `min_cluster_size`; pembanding LDA/NMF. Dua orang petakan
topik → aspek `A1–A8 / S1–S3` → `topic_to_aspect.csv`. Data > 2024 **tidak** dipakai melatih topik;
nanti diklasifikasi oleh klasifier aspek terawasi + IndoBERT.

**Selesai bila:** 20–40 topik; coherence/diversity/stabilitas 5-seed terlapor; ≥85% kalimat
terpetakan ke aspek ≠ S3.

**Risiko:** (a) butuh unduh model embedding (~1 GB) & GPU membantu; (b) topik tak stabil antar-seed
→ laporkan Jaccard; (c) drift topik antar-tahun → justru alasan klasifier aspek dibekukan, bukan refit.

---

## Fase 7 — Anotasi gold (+ silver LLM opsional)

**Notebook:** `07_annotation.ipynb` · **Modul:** `src/labels.py` (baru)

Siapkan sampel berstrata (tahun × bank × petunjuk aspek), ekspor ke format Label Studio/Doccano/CSV.
Target awalmu: **~300 berita** dilabeli manual bersama rekan (gold). Dua annotator → Cohen's κ →
adjudikasi. **Silver (LLM) di-desain sebagai modul opsional yang bisa dinyalakan di tengah jalan**:
prompt + batch + aturan "pakai hanya bila ≥2/3 varian sepakat", divalidasi ke gold-dev.

**Selesai bila:** κ aspek & sentimen ≥ 0.70; gold-dev/test terbagi; (bila dipakai) silver tervalidasi.

**Risiko:** κ rendah → pedoman anotasi perlu iterasi (ronde pilot 50 kalimat dulu); LLM butuh
persetujuan dosen + kunci API → sudah dibuat opsional agar tak memblok jalur manual.

---

## Fase 8 — ABSA IndoBERT

**Notebook:** `08_absa_indobert.ipynb` · **Modul:** `src/absa.py` (baru)

Formulasi *auxiliary sentence*: `[CLS] kalimat [SEP] bank: X ; aspek: Y [SEP]` → 3 kelas.
Fine-tune `indobenchmark/indobert-base-p1` pada data (gold + silver). Klasifikasi aspek +
sentimen untuk **seluruh data terproses** (termasuk > 2023). Keluaran: `p_neg/p_neu/p_pos`,
`score = p_pos − p_neg`, `aspect` per pasangan kalimat–bank.

**Selesai bila:** macro-F1 aspek & sentimen dilaporkan di gold-test; stabilitas antar-periode dicek.

**Risiko:** butuh GPU untuk fine-tune nyaman (CPU lambat tapi bisa untuk prototipe); ketidakseimbangan
kelas → class weight/focal loss.

---

## Fase 9 — Agregasi final

**Notebook:** `09_aggregate.ipynb` · **Modul:** `src/features.py` (baru)

Agregasi `sentence_bank` berlabel → **berita × bank × aspek**:
`count` = jumlah kalimat aspek itu untuk bank itu dalam berita itu;
`score` = agregat (mean/weighted) `p_pos − p_neg`; sertakan `published_at`, `tier`, `weight`.
Simpan parquet + hash.

**Selesai bila:** tabel final tervalidasi (tak ada bocor dari harga; annotator tak lihat harga);
contoh output cocok dengan ilustrasimu ("Kinerja keuangan di 3 kalimat → score X; Kebijakan → score Y").

---

## Catatan lintas-fase

- **Reprodusibilitas:** seed tetap, versi dependensi dikunci, hash dataset per tahap.
- **Anti-kebocoran:** BERTopic & pengembangan taksonomi/anotasi hanya pakai ≤ 2023; annotator
  tak pernah melihat pergerakan harga.
- **Etika:** 1 req/detik, UA riset, simpan HTML hanya untuk riset, publikasi = URL + fitur turunan.
