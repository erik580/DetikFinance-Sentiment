# Justifikasi Penentuan Taksonomi Aspek

**Tujuan:** menentukan taksonomi aspek (A1–A8, S1–S3) dengan **dasar literatur**
(bukan asumsi penulis) — sesuai arahan dosen. Pemetaan tiap topik BERTopic ke aspek
dilakukan secara **manual oleh dua anotator** (penulis + partner), tanpa metode usulan
otomatis.

> Kepatuhan: ringkasan sumber diparafrasekan; sitasi penuh dilakukan di bab metodologi.

---

## 1. Daftar aspek berasal dari studi terpublikasi (bukan dibuat sendiri)

Kategori aspek kita dipetakan dari taksonomi topik berita keuangan yang **sudah dipublikasi
dan dipakai untuk domain yang sama** (berita keuangan Indonesia):

- **Maharani, Yustiawan, Rochim & Purwarianti (2023), "Domain-Specific Language Model
  Post-Training for Indonesian Financial NLP"** (Institut Teknologi Bandung + BRIBRAIN,
  PT Bank Rakyat Indonesia). Studi ini membangun dataset **topic classification** berita
  keuangan Indonesia memakai taksonomi **Twitter Financial News (20 topik)**:
  Analyst Update, Fed & Central Banks, Company & Product News, Treasuries & Corporate Debt,
  Dividend, Earnings, Energy & Oil, Financials, Currencies, General News & Opinion,
  Gold & Metals & Materials, IPO, Legal & Regulation, M&A & Investments, Macro, Markets,
  Politics, Personnel Change, Stock Commentary, Stock Movement. Top-4 terkonsolidasi:
  **Company & Product News, Stock Commentary, Macro, General News & Opinion**. Studi ini juga
  memakai sumber berita yang beririsan dengan kita (termasuk **Detik**).
  Sumber: https://arxiv.org/html/2310.09736v1

  → **Relevansi:** memberi dasar akademik untuk daftar topik keuangan Indonesia. Taksonomi
  kita (A1–A8/S1–S3) adalah **spesialisasi** dari daftar ini ke konteks 4 bank target.

- **Twitter Financial News Topic dataset** (zeroshot/twitter-financial-news-topic): taksonomi
  20-topik standar yang menjadi basis studi di atas.

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

## 2. Penemuan topik: BERTopic (data-driven)

Topik ditemukan secara **tak-terawasi** dengan **BERTopic** (embedding `multilingual-e5-base`
+ UMAP + HDBSCAN), dilatih pada kalimat Tier A/B dengan `published_at ≤ 2024-12-31`
(kontrol anti-kebocoran). Dibandingkan dengan LDA sebagai pembanding klasik (coherence,
diversity, stabilitas). Topik yang dihasilkan **bukan** ditentukan penulis — melainkan muncul
dari data.

Dukungan: BERTopic (Grootendorst, 2022); perbandingan dengan LDA sebagai baseline klasik.

---

## 3. Pemetaan topik → aspek: MANUAL oleh dua anotator

Setiap topik BERTopic (diwakili 10 kata kunci teratas) dipetakan ke salah satu aspek
(A1–A8/S1–S3) **secara manual** oleh dua anotator yang bekerja **independen**, lalu
direkonsiliasi. Prosedur:

1. Jalankan BERTopic → `data/processed/topic_to_aspect.csv` berisi `topic_id`, `count`,
   `keywords` (kata kunci tiap topik), dan kolom kosong `aspect_annotator_1/2/final`.
2. Dua anotator mengisi `aspect_annotator_1` dan `aspect_annotator_2` **independen**
   (melihat kata kunci + daftar aspek berbasis studi acuan di Bagian 1).
3. Rekonsiliasi perbedaan → `aspect_final`.
4. Hitung **Cohen's κ** antar-anotator (reliabilitas antar-penilai); target ≥ 0,70.
5. Syarat kecukupan (spec): ≥ 85% kalimat terpetakan ke aspek ≠ S3.

Dasar daftar aspek (Bagian 1) + penemuan topik otomatis (Bagian 2) memastikan pemetaan
manual ini **tidak bermula dari asumsi penulis**: kategori sudah berdasar literatur, dan
topik berasal dari data; anotator hanya menautkan keduanya dengan penilaian ahli domain.

---

## 4. Ringkasan tiga lapis justifikasi

| Lapis | Komponen | Dasar |
|---|---|---|
| 1. Daftar aspek | A1–A8/S1–S3 | studi terpublikasi domain-sama (Maharani dkk. 2023; Twitter Fin News) |
| 2. Penemuan topik | BERTopic (vs LDA) | tak-terawasi, data-driven; Grootendorst 2022 |
| 3. Pemetaan topik→aspek | manual 2 anotator + Cohen's κ | penilaian ahli dengan reliabilitas terukur |

**Catatan:** semua sumber perlu dibaca langsung dan disitasi penuh pada bab metodologi.
Isi ringkasan ini telah diparafrasekan untuk kepatuhan lisensi.
