# Justifikasi & Metode Penentuan Taksonomi Aspek

**Tujuan:** menentukan taksonomi aspek (A1–A8, S1–S3) dengan **dasar literatur** dan
**metode data-driven**, bukan asumsi penulis — sesuai arahan dosen.

> Kepatuhan: ringkasan sumber diparafrasekan; sitasi penuh dilakukan di bab metodologi.

---

## 1. Taksonomi berasal dari studi terpublikasi (bukan dibuat sendiri)

Aspek kita dipetakan dari taksonomi topik berita keuangan yang **sudah dipublikasi dan
dipakai untuk domain yang sama** (berita keuangan Indonesia):

- **Maharani, Yustiawan, Rochim & Purwarianti (2023), "Domain-Specific Language Model
  Post-Training for Indonesian Financial NLP"** (Institut Teknologi Bandung + BRIBRAIN,
  PT Bank Rakyat Indonesia). Studi ini membangun dataset **topic classification** berita
  keuangan Indonesia memakai taksonomi **Twitter Financial News (20 topik)**:
  Analyst Update, Fed & Central Banks, Company & Product News, Treasuries & Corporate Debt,
  Dividend, Earnings, Energy & Oil, Financials, Currencies, General News & Opinion,
  Gold & Metals & Materials, IPO, Legal & Regulation, M&A & Investments, Macro, Markets,
  Politics, Personnel Change, Stock Commentary, Stock Movement. Top-4 terkonsolidasi:
  **Company & Product News, Stock Commentary, Macro, General News & Opinion**.
  Mereka juga memakai sumber berita yang beririsan dengan kita (termasuk **Detik**).
  Sumber: https://arxiv.org/html/2310.09736v1

  → **Relevansi:** memberi dasar akademik untuk daftar topik keuangan Indonesia. Taksonomi
  kita (A1–A8/S1–S3) adalah **spesialisasi** dari daftar ini ke konteks 4 bank, dengan
  kolom `maps_from` di `src/aspect_taxonomy.py` menautkan tiap aspek kita ke label studi acuan.

- **Twitter Financial News Topic dataset (zeroshot/twitter-financial-news-topic).** Taksonomi
  20-topik yang menjadi basis studi di atas; dirujuk sebagai sumber label standar industri.

### Pemetaan aspek kita → label studi acuan
| Kode | Aspek (kita) | Berasal dari (Twitter Fin News / Maharani 2023) |
|---|---|---|
| A1 | Kinerja keuangan | Earnings; Financials |
| A2 | Kualitas aset & risiko kredit | Financials (risiko kredit, domain perbankan) |
| A3 | Aksi korporasi & dividen | Dividend; M&A & Investments; Treasuries & Corporate Debt |
| A4 | Penyaluran kredit & ekspansi | Company & Product News |
| A5 | Kebijakan & regulasi | Fed & Central Banks; Legal & Regulation |
| A6 | Digital & operasional | Company & Product News (lini digital) |
| A7 | Pandangan analis & valuasi | Analyst Update; Stock Commentary |
| A8 | Tata kelola, hukum & reputasi | Legal & Regulation; Personnel Change |
| S1 | Market wrap & arus transaksi | Markets; Stock Movement |
| S2 | Makro & umum | Macro; Currencies; General News |
| S3 | Lainnya | General News & Opinion (residual) |

---

## 2. Metode data-driven: BERTopic + similarity (Sentence-BERT/e5)

Alih-alih menebak aspek tiap topik secara subjektif, kita memakai **cosine similarity
embedding** (saran dosen: SentenceBERT/similarity):

1. **BERTopic** (Fase 6) menemukan topik dari kalimat secara tak-terawasi → tiap topik
   diwakili 10 kata kunci.
2. Tiap **definisi aspek** (ASPECT_DEFINITIONS) di-embed dengan model yang sama (e5-base).
3. Tiap **topik** di-embed dari kata kuncinya.
4. Hitung **cosine similarity** topik ↔ tiap aspek → aspek dengan skor tertinggi menjadi
   **usulan otomatis**, disertai 3 kandidat teratas + `margin` (selisih skor top-1 dan
   top-2) sebagai ukuran keyakinan.

Pendekatan ini mengubah pemetaan dari "pendapat" menjadi **ukuran kuantitatif yang
dapat direproduksi**, lalu divalidasi anotator (gold).

### Dukungan literatur untuk pendekatan embedding-similarity
- **Sentence-BERT (Reimers & Gurevych, 2019)**: embedding kalimat untuk perbandingan
  similarity semantik secara efisien — fondasi metode ini.
- **BERTopic (Grootendorst, 2022)**: topic modelling berbasis embedding + c-TF-IDF.
- **Financial word embeddings (arXiv 1704.05091)**: embedding domain-keuangan menangkap
  kemiripan semantik istilah finansial — mendukung pemakaian similarity di domain ini.

---

## 3. Hasil pilot (uji metode)

Dijalankan via `notebooks/06b_aspect_mapping_pilot.ipynb` (model kecil multilingual untuk
uji logika; produksi memakai e5-base). Topik sintetik yang mewakili tiap aspek terpetakan
**benar** dengan keyakinan tinggi:

| Kata kunci topik | Usulan | Similarity | Benar? |
|---|---|---|---|
| laba bersih pendapatan bunga kuartal | A1 | 0.59 | ✅ |
| npl kredit macet restrukturisasi | A2 | 0.66 | ✅ |
| dividen rups buyback | A3 | 0.75 | ✅ |
| bi rate suku bunga ojk | A5 | 0.70 | ✅ |
| ihsg ditutup gainers net buy asing | S1 | 0.58 | ✅ |
| inflasi rupiah kurs makro | S2 | 0.77 | ✅ |

Topik nyata "agenbrilink desa cabang layanan perbankan" → usulan **A6** (0.42) dengan **A4**
sebagai kandidat alternatif — metode **menyurfacekan ambiguitas** (ekspansi jaringan vs
operasional), bukan menyembunyikannya, sehingga anotator memutuskan berdasar bukti.

---

## 4. Prosedur final (menggabungkan metode + validasi manusia)

1. Jalankan pemetaan similarity → `topic_to_aspect_suggested.csv` (usulan + skor + margin).
2. Dua anotator me-review usulan **secara independen** (terutama topik dengan `margin` kecil
   = ambigu), mengoreksi bila perlu → `aspect_annotator_1/2`.
3. Rekonsiliasi → `aspect_final`; hitung Cohen's κ antar-anotator.
4. Syarat (spec): ≥ 85% kalimat terpetakan ke aspek ≠ S3.

Dengan ini, taksonomi punya **tiga lapis justifikasi**: (a) berasal dari studi terpublikasi
domain-sama, (b) dipetakan dengan metode kuantitatif reproducible, (c) divalidasi anotator.
