"""
Runner crawl L0 -> L1 -> L2 yang checkpoint-able (task 1.5).

L0  : iterasi tanggal, crawl semua halaman indeks, simpan HTML indeks (gz) +
      kumpulkan metadata/link SEMUA artikel -> tabel link (parquet + xlsx).
L1  : seleksi kandidat relevan (judul/subchannel memuat alias bank / kata kebijakan /
      sub-kanal bursa / IHSG-rupiah-inflasi) + sampel acak non-kandidat (kontrol negatif).
L2  : unduh HTML lengkap (gz) HANYA untuk kandidat; parse teks -> news_clean awal.

Checkpoint: progres per-tanggal dicatat di data/interim/crawl_checkpoint.json sehingga
proses bisa dihentikan & dilanjutkan tanpa mengulang hari yang sudah selesai.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .crawl import (
    Crawler,
    article_html_path,
    article_html_relpath,
    index_html_path,
    save_html_gz,
)
from .parse import parse_article, parse_index


# ---------------------------------------------------------------------- #
# util tanggal
# ---------------------------------------------------------------------- #
def daterange(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------------- #
# seleksi kandidat L1
# ---------------------------------------------------------------------- #
@dataclass
class L1Rules:
    bank_patterns: list[str]
    group_patterns: list[str]
    policy_patterns: list[str]
    market_patterns: list[str]
    bursa_subchannels: tuple[str, ...] = ("bursa-valas", "market-research")
    negative_sample_rate: float = 0.02  # kontrol negatif

    def compiled(self) -> list[re.Pattern]:
        pats = (
            self.bank_patterns
            + self.group_patterns
            + self.policy_patterns
            + self.market_patterns
        )
        return [re.compile(p, re.IGNORECASE) for p in pats]

    def is_candidate(self, title: str, subchannel: Optional[str]) -> bool:
        if subchannel in self.bursa_subchannels:
            return True
        text = title or ""
        return any(p.search(text) for p in self.compiled())


def build_l1_rules(aliases: dict) -> L1Rules:
    bank = [p for pats in aliases["banks"].values() for p in pats]
    return L1Rules(
        bank_patterns=bank,
        group_patterns=aliases.get("group", []),
        policy_patterns=aliases.get("policy_keywords", []),
        market_patterns=aliases.get("market_keywords", []),
    )


# ---------------------------------------------------------------------- #
# checkpoint
# ---------------------------------------------------------------------- #
class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        self.done_days: set[str] = set()
        if path.exists():
            self.done_days = set(json.loads(path.read_text()).get("done_days", []))

    def mark(self, day: date) -> None:
        self.done_days.add(day.isoformat())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"done_days": sorted(self.done_days)}))

    def has(self, day: date) -> bool:
        return day.isoformat() in self.done_days


# ---------------------------------------------------------------------- #
# runner utama
# ---------------------------------------------------------------------- #
@dataclass
class CrawlPaths:
    raw: Path
    interim: Path

    @property
    def checkpoint(self) -> Path:
        return self.interim / "crawl_checkpoint.json"

    @property
    def links_parquet(self) -> Path:
        return self.interim / "news_links.parquet"

    @property
    def clean_parquet(self) -> Path:
        return self.interim / "news_clean_raw.parquet"


def run_crawl(
    crawler: Crawler,
    selectors: dict,
    l1: L1Rules,
    paths: CrawlPaths,
    start: date,
    end: date,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """Jalankan crawl L0->L2 dari start..end (inklusif). Idempoten via checkpoint."""
    random.seed(seed)
    ckpt = Checkpoint(paths.checkpoint)

    # muat hasil sebelumnya agar bisa dilanjutkan
    link_rows: list[dict] = []
    clean_rows: list[dict] = []
    if paths.links_parquet.exists():
        link_rows = pd.read_parquet(paths.links_parquet).to_dict("records")
    if paths.clean_parquet.exists():
        clean_rows = pd.read_parquet(paths.clean_parquet).to_dict("records")

    stats = {"days": 0, "links": 0, "candidates": 0, "html_saved": 0, "parse_fail": 0}

    for day in daterange(start, end):
        if ckpt.has(day):
            continue

        # ---- L0: semua halaman indeks hari ini ----
        day_items = []
        for page in range(1, 50):
            html = crawler.fetch_index_page(day, page)
            if page == 1 or len(day_items) == 0:
                save_html_gz(html, index_html_path(paths.raw, day, page))
            items = parse_index(html, selectors)
            if not items:
                break
            day_items.extend(items)

        for it in day_items:
            candidate = l1.is_candidate(it.title, it.subchannel)
            # kontrol negatif: ambil sebagian kecil non-kandidat
            if not candidate and random.random() < l1.negative_sample_rate:
                candidate = True
                neg_control = True
            else:
                neg_control = not candidate and False

            link_rows.append(
                {
                    "article_id": it.article_id,
                    "url": it.url,
                    "title": it.title,
                    "subchannel": it.subchannel,
                    "date_text": it.date_text,
                    "index_date": day.isoformat(),
                    "html_path": article_html_relpath(it.article_id),
                    "is_candidate": candidate,
                    "neg_control": neg_control,
                    "html_saved": False,
                }
            )

            # ---- L2: unduh HTML hanya untuk kandidat ----
            if candidate:
                stats["candidates"] += 1
                try:
                    ahtml = crawler.fetch_article(it.url)
                    save_html_gz(ahtml, article_html_path(paths.raw, it.article_id))
                    art = parse_article(ahtml, it.url, selectors)
                    link_rows[-1]["html_saved"] = True
                    stats["html_saved"] += 1
                    clean_rows.append(
                        {
                            "article_id": art.article_id,
                            "url": art.url,
                            "title": art.title,
                            "published_at": art.published_at,
                            "subchannel": art.subchannel,
                            "n_words": art.n_words,
                            "body_text": art.body_text,
                            "index_date": day.isoformat(),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    stats["parse_fail"] += 1
                    if verbose:
                        print(f"  [WARN] gagal {it.url}: {exc}")

        stats["days"] += 1
        stats["links"] = len(link_rows)
        ckpt.mark(day)

        # tulis checkpoint data tiap hari (aman bila terputus)
        pd.DataFrame(link_rows).to_parquet(paths.links_parquet, index=False)
        if clean_rows:
            pd.DataFrame(clean_rows).to_parquet(paths.clean_parquet, index=False)
        if verbose:
            print(
                f"{day}: {len(day_items)} link, "
                f"kandidat kumulatif {stats['candidates']}, "
                f"HTML tersimpan {stats['html_saved']}"
            )

    # ekspor Excel sekali di akhir untuk kemudahan akses
    links_df = pd.DataFrame(link_rows)
    links_df.to_excel(paths.interim / "news_links.xlsx", index=False)
    return stats
