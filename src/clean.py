"""
Fase 3 — Cleaning & deduplikasi berita.

Input : news_clean_raw.parquet (hasil parse HTML kandidat, Fase 2)
Output: news_clean.parquet (teks bersih, bebas duplikat, siap tiering Fase 4)

Langkah:
  1. Normalisasi Unicode (NFKC) + rapikan spasi
  2. Buang boilerplate (pola di config/boilerplate_patterns.txt + dateline awal)
  3. Filter: < min_words kata, advertorial
  4. Dedup eksak: hash(judul+teks ternormalisasi), simpan terbit paling awal
  5. Dedup mirip (near-duplicate): MinHash LSH, Jaccard >= thr, jendela +/- window hari
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------- #
# 1. normalisasi
# ---------------------------------------------------------------------- #
def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\u00a0", " ")           # non-breaking space
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


# ---------------------------------------------------------------------- #
# 2. boilerplate
# ---------------------------------------------------------------------- #
def load_boilerplate_patterns(path: Path) -> list[re.Pattern]:
    pats: list[re.Pattern] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pats.append(re.compile(line, re.IGNORECASE))
    return pats


# dateline di AWAL teks: "Jakarta -", "Jakarta, CNBC -", dsb (nama kota + strip)
_DATELINE = re.compile(r"^[A-Z][A-Za-z .,'()/-]{1,40}?\s[-–]\s")


def strip_boilerplate(text: str, patterns: list[re.Pattern]) -> str:
    t = text
    for p in patterns:
        t = p.sub(" ", t)
    t = _DATELINE.sub("", t, count=1)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


# ---------------------------------------------------------------------- #
# dedup helpers
# ---------------------------------------------------------------------- #
def _exact_key(title: str, body: str) -> str:
    norm = re.sub(r"\W+", " ", f"{title} {body}".lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()


def _shingles(text: str, k: int = 5) -> set[str]:
    words = re.sub(r"\W+", " ", text.lower()).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


# ---------------------------------------------------------------------- #
# config
# ---------------------------------------------------------------------- #
@dataclass
class CleanConfig:
    min_words: int = 40
    exclude_subchannels: tuple[str, ...] = ("foto-bisnis", "video")
    advertorial_tags: tuple[str, ...] = ("advertorial", "sponsored", "adv")
    near_dup_threshold: float = 0.8
    near_dup_window_days: int = 2
    shingle_k: int = 5
    boilerplate_path: Optional[Path] = None


# ---------------------------------------------------------------------- #
# pipeline utama
# ---------------------------------------------------------------------- #
def clean_news(df: pd.DataFrame, cfg: CleanConfig) -> tuple[pd.DataFrame, dict]:
    """Kembalikan (df_bersih, statistik)."""
    stats: dict[str, int] = {"input": len(df)}
    out = df.copy()

    patterns = (
        load_boilerplate_patterns(cfg.boilerplate_path)
        if cfg.boilerplate_path and cfg.boilerplate_path.exists()
        else []
    )

    # 1-2. normalisasi + boilerplate
    out["body_text"] = out["body_text"].map(normalize_text)
    out["body_text"] = out["body_text"].map(lambda t: strip_boilerplate(t, patterns))
    out["title"] = out["title"].map(normalize_text)
    out["n_words"] = out["body_text"].str.split().map(len)

    # 3. filter subchannel foto/video
    before = len(out)
    out = out[~out["subchannel"].isin(cfg.exclude_subchannels)]
    stats["drop_subchannel"] = before - len(out)

    # 3. filter advertorial (deteksi dari url/subchannel/judul)
    before = len(out)
    adv_rx = re.compile("|".join(cfg.advertorial_tags), re.IGNORECASE)
    is_adv = (
        out["url"].fillna("").str.contains(adv_rx)
        | out["subchannel"].fillna("").str.contains(adv_rx)
    )
    out = out[~is_adv]
    stats["drop_advertorial"] = before - len(out)

    # 3. filter < min_words
    before = len(out)
    out = out[out["n_words"] >= cfg.min_words]
    stats["drop_too_short"] = before - len(out)

    # urutkan agar yang terbit paling awal dipertahankan saat dedup
    out = out.sort_values("published_at").reset_index(drop=True)

    # 4. dedup eksak
    before = len(out)
    out["_exact"] = [_exact_key(t, b) for t, b in zip(out["title"], out["body_text"])]
    out = out.drop_duplicates("_exact", keep="first")
    stats["drop_exact_dup"] = before - len(out)

    # 5. dedup near-duplicate (MinHash LSH)
    out, n_near = _dedup_near(out, cfg)
    stats["drop_near_dup"] = n_near

    out = out.drop(columns=["_exact"]).reset_index(drop=True)
    out["dup_cluster_id"] = range(len(out))  # placeholder id unik pasca-dedup
    stats["output"] = len(out)
    stats["dup_ratio_pct"] = round(
        100 * (stats["drop_exact_dup"] + stats["drop_near_dup"]) / max(before, 1), 2
    )
    return out, stats


def _dedup_near(df: pd.DataFrame, cfg: CleanConfig) -> tuple[pd.DataFrame, int]:
    """Buang near-duplicate dengan MinHash LSH dalam jendela waktu +/- window hari."""
    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        return df, 0  # jika lib tak ada, lewati (tetap aman)

    df = df.copy()
    df["_pub"] = pd.to_datetime(df["published_at"], errors="coerce")
    df = df.sort_values("_pub").reset_index(drop=True)

    lsh = MinHashLSH(threshold=cfg.near_dup_threshold, num_perm=128)
    minhashes: dict[int, "MinHash"] = {}
    pub_times: dict[int, pd.Timestamp] = {}
    drop_idx: set[int] = set()
    window = pd.Timedelta(days=cfg.near_dup_window_days)

    for idx, row in df.iterrows():
        sh = _shingles(row["body_text"], cfg.shingle_k)
        if not sh:
            continue
        m = MinHash(num_perm=128)
        for s in sh:
            m.update(s.encode("utf-8"))

        # cari kandidat mirip yang terbit dalam jendela waktu
        for cand in lsh.query(m):
            if cand in drop_idx:
                continue
            if pd.notna(row["_pub"]) and pd.notna(pub_times.get(cand)):
                if abs(row["_pub"] - pub_times[cand]) <= window:
                    drop_idx.add(idx)       # buang yang lebih baru (idx), simpan cand
                    break
        else:
            lsh.insert(idx, m)
            minhashes[idx] = m
            pub_times[idx] = row["_pub"]

    kept = df.drop(index=list(drop_idx)).drop(columns=["_pub"]).reset_index(drop=True)
    return kept, len(drop_idx)
