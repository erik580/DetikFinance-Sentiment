# Justifikasi Skema Tiering Relevansi (A/B/C/D)

**Tujuan dokumen:** memberi dasar ilmiah untuk skema tiering relevansi berita per bank
(bukan asumsi penulis), sebagaimana diminta dosen pembimbing. Setiap keputusan desain
ditautkan ke literatur.

> Catatan kepatuhan: ringkasan di bawah diparafrasekan dari sumber aslinya untuk mematuhi
> batas pengutipan; silakan verifikasi langsung ke sumber saat menulis bab metodologi.

---

## 1. Masalah: kenapa berita perlu disaring & diberi tingkat relevansi

Merata-ratakan semua berita menjadi satu skor sentimen harian **menenggelamkan sinyal**.
Dasar teoretisnya kuat:

- **Boudoukh, Feldman, Kogan & Richardson (2019), "Which News Moves Stock Prices?"**
  (NBER WP 18725; *Review of Financial Studies*). Temuan kunci: ketika berita *diidentifikasi
  relevansinya* lebih dulu, hubungan antara berita dan pergerakan harga jauh lebih kuat.
  Berita yang **teridentifikasi** menyumbang **49,6%** volatilitas idiosinkratik semalam
  (vs 12,4% saat jam bursa), dan hari dengan berita **tak teridentifikasi** berperilaku
  mirip hari **tanpa berita**. → **Implikasi untuk kita:** menyaring & memberi tingkat
  relevansi (tiering) bukan sekadar preferensi, melainkan prasyarat agar sinyal sentimen
  tidak hilang. Berita yang tidak jelas relevansinya setara dengan noise.
  Sumber: https://www.nber.org/system/files/working_papers/w18725/w18725.pdf

- **"A Framework for Measuring How News Topics Drive Stock Movement" (arXiv 2510.06864,
  2024).** Menyoroti bahwa mayoritas studi mengagregasi sentimen harian jadi satu skor dan
  mengabaikan variasi **konten topik dan relevansi**. → mendukung desain kita: relevansi
  per-berita + per-topik, bukan satu skor.
  Sumber: https://arxiv.org/html/2510.06864v1

- **"Quantitative Analysis of Media Bias and Stock Price Dynamics" (arXiv 2608.05899).**
  Setelah korpus **disaring untuk menyisakan liputan firm-specific yang materially relevant**,
  barulah ukuran stance harian dibangun. → praktik menyaring relevansi firm-specific sebelum
  mengukur sentimen adalah prosedur yang lazim di literatur.
  Sumber: https://arxiv.org/html/2608.05899

---

## 2. Dasar untuk STRUKTUR BERTINGKAT (firm → sektor → pasar/makro)

Hierarki Tier A (bank spesifik) → B (sektor/grup perbankan) → C (pasar/makro) **bukan
rekaan kita**, melainkan mencerminkan taksonomi relevansi berita yang sudah dipakai di
literatur text-mining keuangan:

- **"Predicting Stock Price Movements Based on Different Categories of News Articles"
  (IEEE SSCI 2015).** Mengkategorikan berita berdasarkan kedekatannya dengan saham:
  **stock → sub-industry → industry → group industry → sector**, dan memakai kernel
  terpisah untuk tiap level. → **justifikasi langsung** bahwa relevansi berita berjenjang
  (dari spesifik-perusahaan sampai sektor) adalah skema yang mapan. Tier A/B/C kita adalah
  penyederhanaan skema berjenjang ini ke konteks 4 bank + sektor perbankan + pasar.
  Sumber: http://vigir.missouri.edu/~gdesouza/Research/Conference_CDs/IEEE_SSCI_2015/data/7560a703.pdf

- **FinBERT filtering tiers (praktik industri).** Pendekatan penyaringan berita per emiten
  memakai **tiga tingkat istilah pencarian**: (1) kode ticker, (2) nama kanonik perusahaan,
  (3) sinonim/singkatan. → sejalan dengan kamus alias berjenjang kita (BBCA/BCA/Bank Central
  Asia) dan menegaskan bahwa pencocokan alias bertingkat adalah praktik umum.

---

## 3. Dasar untuk SKOR relevansi (judul vs isi, posisi & frekuensi sebutan)

Pemberian bobot berbeda pada sebutan di **judul** vs **isi**, serta memanfaatkan **frekuensi
sebutan**, didukung oleh:

- **Relevance Theory & newsworthiness pada headline berita** (ResearchGate, 2021):
  judul berita dikemas untuk memadatkan informasi paling penting. → wajar memberi bobot
  tertinggi pada sebutan bank di **judul** (bobot 3 pada skema kita).

- **"Repurposing Attention Weights to Assess News Relevance" (arXiv 2001.09466, EMNLP
  ECONLP).** Relevansi berita terhadap saham dapat diperingkat; peringkat relevansi
  berkorelasi positif dengan akurasi prediksi harga. → mendukung gagasan **skor relevansi
  kontinu** (bukan biner), persis seperti `s_b` kita.
  Sumber: https://arxiv.org/html/2001.09466v3

- **Company mention detection (Columbia/Brandeis, SciTePress 2014).** Deteksi sebutan
  perusahaan (NER + koreferensi) memperbaiki analitik keuangan; cakupan sebutan penting.
  → mendukung penghitungan **jumlah sebutan di badan** (dengan cap) sebagai komponen skor,
  dan penanganan koreferensi/anafora (link `inherited` pada pipeline kita).

### Pemetaan ke rumus skor kita
```
s_b = 3·[bank di judul] + 2·[bank di 3 kalimat awal] + min(sebutan badan, 3)
```
| Komponen | Bobot | Dasar |
|---|---|---|
| Sebutan di judul | 3 (tertinggi) | Relevance Theory: judul memadatkan info terpenting |
| Sebutan di 3 kalimat awal (lead) | 2 | Struktur piramida terbalik jurnalistik: info utama di awal |
| Frekuensi sebutan di badan (cap 3) | +1 per sebutan | Company-mention coverage memperbaiki sinyal; cap mencegah dominasi artikel panjang |

Ambang **Tier A = s_b ≥ 3** memastikan minimal setara "disebut cukup sering di badan" atau
"muncul di judul" — garis pemisah yang dapat dipertanggungjawabkan, bukan sembarang.

---

## 4. Dasar untuk BOBOT grup 0,5 (Tier B)

Berita sektor/grup (Himbara/bank BUMN) memengaruhi semua anggota tetapi **lebih lemah**
daripada berita firm-specific. Ini sejalan dengan taksonomi berjenjang (level sektor < level
firm dalam kedekatan ke saham tertentu; IEEE SSCI 2015) dan dengan temuan Boudoukh dkk.
bahwa sinyal terkuat berasal dari berita yang teridentifikasi spesifik. Bobot 0,5 adalah
**hiperparameter** yang: (a) lebih kecil dari firm-specific (1,0), (b) akan diuji sensitivitasnya
pada tahap pemodelan (mis. 0,25/0,5/0,75) sebagai analisis ketahanan.

---

## 5. Ringkasan tabel justifikasi

| Keputusan desain | Dasar literatur |
|---|---|
| Perlu menyaring & memberi tingkat relevansi | Boudoukh dkk. 2019; arXiv 2608.05899; arXiv 2510.06864 |
| Struktur berjenjang firm→sektor→pasar (Tier A/B/C) | IEEE SSCI 2015 (stock→industry→sector) |
| Alias bertingkat (ticker/nama/sinonim) | praktik FinBERT filtering 3-tier |
| Bobot judul > lead > badan | Relevance Theory headline; piramida terbalik |
| Skor relevansi kontinu & cap frekuensi | arXiv 2001.09466; SciTePress 2014 company mention |
| Bobot grup 0,5 (diuji sensitivitas) | taksonomi berjenjang + hiperparameter |

**Catatan:** semua sumber di atas perlu dibaca langsung dan disitasi penuh dengan gaya sitasi
yang disyaratkan. Isi ringkasan ini telah diparafrasekan untuk kepatuhan lisensi.
