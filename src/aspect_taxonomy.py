"""
Penentuan taksonomi aspek secara DATA-DRIVEN (bukan asumsi penulis).

Metode (sesuai saran dosen):
  1. Taksonomi KANDIDAT berasal dari STUDI yang sudah dipublikasi untuk domain yang sama
     (berita keuangan Indonesia), bukan dibuat sendiri. Lihat ASPECT_DEFINITIONS &
     sumbernya di docstring + reports/justifikasi_aspek.md.
  2. Pemetaan topik BERTopic -> aspek dengan SIMILARITY embedding (Sentence-BERT / e5):
     embed kata kunci tiap topik, embed definisi tiap aspek, ambil cosine similarity
     tertinggi. Ini mengganti tebakan subjektif dengan ukuran kuantitatif + bukti.

Hasil: usulan pemetaan topik->aspek beserta skor similarity & kandidat-2 teratas,
sebagai bahan objektif yang lalu divalidasi anotator (gold).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------- #
# Taksonomi aspek KANDIDAT dengan DASAR LITERATUR
# ---------------------------------------------------------------------- #
# Sumber utama taksonomi topik keuangan:
#  - Maharani, Yustiawan, Rochim, Purwarianti (2023), "Domain-Specific Language Model
#    Post-Training for Indonesian Financial NLP" (ITB + BRIBRAIN). Memakai taksonomi
#    Twitter Financial News (20 topik): Analyst Update, Fed & Central Banks,
#    Company & Product News, Treasuries & Corporate Debt, Dividend, Earnings,
#    Energy & Oil, Financials, Currencies, General News & Opinion,
#    Gold & Metals & Materials, IPO, Legal & Regulation, M&A & Investments, Macro,
#    Markets, Politics, Personnel Change, Stock Commentary, Stock Movement.
#    Top-4 terkonsolidasi: Company & Product News, Stock Commentary, Macro, General News.
#    Sumber: https://arxiv.org/html/2310.09736v1
#
# Taksonomi kita (A1-A8/S1-S3) adalah pemetaan topik-topik tsb ke konteks SPESIFIK
# perbankan Indonesia. Kolom "maps_from" menautkan tiap aspek kita ke label studi acuan.

ASPECT_DEFINITIONS = {
    "A1": {
        "name": "Kinerja keuangan",
        # definisi dipakai untuk embedding -> similarity dengan kata kunci topik
        "definition": "laba bersih pendapatan bunga margin NIM ROE aset laporan keuangan "
                      "pertumbuhan laba kinerja kuartalan earnings",
        "maps_from": "Earnings; Financials (Twitter Fin News / Maharani 2023)",
    },
    "A2": {
        "name": "Kualitas aset & risiko kredit",
        "definition": "NPL kredit bermasalah kredit macet restrukturisasi pencadangan "
                      "CKPN rasio kredit risiko kredit kualitas aset",
        "maps_from": "Financials/credit risk (domain perbankan)",
    },
    "A3": {
        "name": "Aksi korporasi & dividen",
        "definition": "dividen buyback stock split rights issue akuisisi merger obligasi "
                      "RUPS aksi korporasi pembagian dividen",
        "maps_from": "Dividend; M&A & Investments; Treasuries & Corporate Debt",
    },
    "A4": {
        "name": "Penyaluran kredit & ekspansi",
        "definition": "penyaluran kredit pertumbuhan kredit DPK KUR KPR UMKM ekspansi "
                      "produk baru jaringan agen cabang ekspansi bisnis",
        "maps_from": "Company & Product News",
    },
    "A5": {
        "name": "Kebijakan & regulasi",
        "definition": "BI Rate suku bunga acuan OJK LPS GWM kebijakan pemerintah regulasi "
                      "bank sentral moneter aturan perbankan",
        "maps_from": "Fed & Central Banks; Legal & Regulation",
    },
    "A6": {
        "name": "Digital & operasional",
        "definition": "mobile banking aplikasi digital QRIS layanan digital gangguan "
                      "sistem keamanan siber fraud transformasi digital operasional",
        "maps_from": "Company & Product News (digital)",
    },
    "A7": {
        "name": "Pandangan analis & valuasi",
        "definition": "rekomendasi beli jual target harga valuasi analis sekuritas "
                      "proyeksi harga saham rating saham",
        "maps_from": "Analyst Update; Stock Commentary",
    },
    "A8": {
        "name": "Tata kelola, hukum & reputasi",
        "definition": "kasus hukum sanksi pergantian direksi komisaris tata kelola "
                      "pelanggaran etika reputasi gugatan",
        "maps_from": "Legal & Regulation; Personnel Change",
    },
    "S1": {
        "name": "Market wrap & arus transaksi",
        "definition": "IHSG ditutup dibuka menguat melemah top gainers losers net buy "
                      "sell asing ringkasan perdagangan pergerakan saham harian",
        "maps_from": "Markets; Stock Movement; Stock Commentary (market wrap)",
    },
    "S2": {
        "name": "Makro & umum",
        "definition": "inflasi kurs rupiah pertumbuhan ekonomi makroekonomi neraca "
                      "perdagangan ekonomi nasional kondisi makro",
        "maps_from": "Macro; Currencies; General News & Opinion",
    },
    "S3": {
        "name": "Lainnya",
        "definition": "berita tidak relevan topik umum lain tidak terkait keuangan bank",
        "maps_from": "General News & Opinion (residual)",
    },
}


@dataclass
class MappingResult:
    table: pd.DataFrame            # topic_id, keywords, aspek top-1/2/3 + skor
    aspect_codes: list[str]


def map_topics_to_aspects(
    topic_model,
    embedder,
    e5_prefix: str = "query: ",
    top_k: int = 3,
) -> MappingResult:
    """Petakan tiap topik BERTopic -> aspek via cosine similarity embedding.

    topic_model : objek BERTopic terlatih
    embedder    : SentenceTransformer (model yang sama dgn Fase 6, mis. e5-base)
    """
    codes = list(ASPECT_DEFINITIONS.keys())
    aspect_texts = [e5_prefix + ASPECT_DEFINITIONS[c]["definition"] for c in codes]
    aspect_emb = embedder.encode(aspect_texts, normalize_embeddings=True)

    rows = []
    for tid in topic_model.get_topics():
        if tid == -1:
            continue
        kws = [w for w, _ in topic_model.get_topic(tid)[:10] if w]
        kw_str = " ".join(kws)
        t_emb = embedder.encode([e5_prefix + kw_str], normalize_embeddings=True)[0]
        sims = aspect_emb @ t_emb  # cosine (sudah dinormalisasi)
        order = np.argsort(sims)[::-1][:top_k]
        row = {"topic_id": tid, "keywords": ", ".join(kws)}
        for rank, idx in enumerate(order, 1):
            row[f"aspect_top{rank}"] = codes[idx]
            row[f"sim_top{rank}"] = round(float(sims[idx]), 3)
        row["aspect_suggested"] = codes[order[0]]      # usulan otomatis
        row["margin"] = round(float(sims[order[0]] - sims[order[1]]), 3)  # keyakinan
        rows.append(row)

    return MappingResult(table=pd.DataFrame(rows), aspect_codes=codes)
