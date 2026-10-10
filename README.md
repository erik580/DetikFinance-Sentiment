# Riset Sentimen Berbasis Topik — Berita DetikFinance (Text Mining)

> Repo: https://github.com/erik580/DetikFinance-Sentiment

Pipeline **text mining** untuk menghasilkan dataset sentimen berbasis topik dari berita
DetikFinance, sebagai data pendukung eksternal untuk model prediksi arah *abnormal return*
saham bank (BBCA, BBRI, BBNI, BMRI). **Scope repo ini berhenti di text mining** — tidak
mencakup data harga, market model, maupun model prediktif.

## Output akhir

Agregat **berita × bank × aspek**, berisi untuk tiap kombinasi:
- `score` — sentiment score (p_pos − p_neg) agregat,
- `count` — berapa kali aspek itu disebut,
- metadata hilir: `published_at`, `tier`/`weight`.

## Roadmap (fase)

| Fase | Notebook | Isi |
|------|----------|-----|
| 0 | `00_pilot_crawl.ipynb` | Pilot crawler: verifikasi struktur HTML, ukur volume & disk |
| 1 | `01_crawl_index.ipynb` | Crawl indeks (L0): simpan link + metadata semua artikel |
| 2 | `02_scrape_articles.ipynb` | Scrape HTML lengkap (L2) + parse teks dari HTML tersimpan |
| 3 | `03_clean_dedup.ipynb` | Cleaning, boilerplate removal, deduplikasi |
| 4 | `04_tiering_relevance.ipynb` | Skor relevansi + Tier A/B/C/D per bank |
| 5 | `05_segment_link.ipynb` | Segmentasi kalimat + entity linking per bank |
| 6 | `06_bertopic.ipynb` | BERTopic (train ≤ 31 Des 2023) → taksonomi aspek |
| 7 | `07_annotation.ipynb` | Gold (manual) + silver (LLM opsional) |
| 8 | `08_absa_indobert.ipynb` | Fine-tune IndoBERT ABSA → klasifikasi sisa data |
| 9 | `09_aggregate.ipynb` | Agregasi final berita × bank × aspek |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Struktur

```
config/      # yaml: tanggal, kamus alias, taksonomi, seed
data/
  raw/       # html_index/, html_article/ (gz) — jangan diubah
  interim/   # news_clean, sentences, sentence_bank (parquet)
  gold/      # gold_pairs, pedoman anotasi
  processed/ # agregat final + hash
notebooks/   # 00..09 per fase
src/         # modul: crawl, parse, clean, tiering, segment, link, ...
reports/     # tabel, gambar, draf
```

## Etika crawling

- Patuhi `robots.txt` DetikFinance; 1 request/detik + jitter; backoff pada 429/503.
- Simpan HTML hanya untuk riset; publikasikan daftar URL + fitur turunan, bukan teks penuh.
