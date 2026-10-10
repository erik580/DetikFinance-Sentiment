"""
Crawler DetikFinance — indeks (L0) dan artikel (L2).

Etika (spec §5.1):
- 1 request/detik + jitter; backoff eksponensial pada 429/503.
- Simpan HTML mentah (gz) agar bisa re-parse tanpa crawl ulang.
- User-Agent mencantumkan identitas riset + kontak.

Pola URL terverifikasi (Okt 2026):
    Indeks  : https://finance.detik.com/indeks?page={n}&date=MM/DD/YYYY
    Artikel : https://finance.detik.com/{subchannel}/d-{article_id}/{slug}
"""
from __future__ import annotations

import gzip
import hashlib
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class RetryableHTTP(Exception):
    """Status yang layak di-retry (429/503/5xx)."""


@dataclass
class CrawlConfig:
    base_url: str = "https://finance.detik.com/indeks"
    date_param_format: str = "%m/%d/%Y"
    user_agent: str = "Mozilla/5.0 (research crawler; contact: ganti@email.anda)"
    request_delay_sec: float = 1.0
    jitter_sec: tuple[float, float] = (0.5, 1.5)
    max_retries: int = 4
    backoff_base_sec: float = 2.0
    timeout_sec: int = 30


@dataclass
class Crawler:
    cfg: CrawlConfig = field(default_factory=CrawlConfig)
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.session.headers.update({"User-Agent": self.cfg.user_agent})

    # ------------------------------------------------------------------ #
    # low-level fetch with polite delay + retry
    # ------------------------------------------------------------------ #
    def _polite_sleep(self) -> None:
        lo, hi = self.cfg.jitter_sec
        time.sleep(self.cfg.request_delay_sec + random.uniform(lo, hi))

    def _fetch(self, url: str) -> str:
        @retry(
            retry=retry_if_exception_type(RetryableHTTP),
            stop=stop_after_attempt(self.cfg.max_retries),
            wait=wait_exponential(multiplier=self.cfg.backoff_base_sec),
            reraise=True,
        )
        def _do() -> str:
            resp = self.session.get(url, timeout=self.cfg.timeout_sec)
            if resp.status_code in (429, 503) or resp.status_code >= 500:
                raise RetryableHTTP(f"{resp.status_code} on {url}")
            resp.raise_for_status()
            return resp.text

        html = _do()
        self._polite_sleep()
        return html

    # ------------------------------------------------------------------ #
    # index (L0)
    # ------------------------------------------------------------------ #
    def index_url(self, day: date, page: int = 1) -> str:
        d = day.strftime(self.cfg.date_param_format)
        return f"{self.cfg.base_url}?page={page}&date={d}"

    def fetch_index_page(self, day: date, page: int = 1) -> str:
        return self._fetch(self.index_url(day, page))

    # ------------------------------------------------------------------ #
    # article (L2)
    # ------------------------------------------------------------------ #
    def fetch_article(self, url: str) -> str:
        # ambil versi "singlepage" bila ada untuk hindari artikel terpecah
        sep = "&" if "?" in url else "?"
        return self._fetch(f"{url}{sep}single=1")


# ---------------------------------------------------------------------- #
# penyimpanan HTML mentah (gz) + id artikel
# ---------------------------------------------------------------------- #
def article_id_from_url(url: str) -> str:
    """ID artikel = segmen d-{digits} bila ada, selain itu hash URL."""
    import re

    m = re.search(r"/d-(\d+)/", url)
    if m:
        return m.group(1)
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def save_html_gz(html: str, path: Path) -> int:
    """Simpan HTML terkompresi gzip. Kembalikan ukuran byte terkompresi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = gzip.compress(html.encode("utf-8"))
    path.write_bytes(data)
    return len(data)


def load_html_gz(path: Path) -> str:
    return gzip.decompress(path.read_bytes()).decode("utf-8")


def index_html_path(root: Path, day: date, page: int) -> Path:
    return root / "html_index" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}" / f"page_{page}.html.gz"


def article_html_path(root: Path, article_id: str) -> Path:
    # shard per 3 digit awal untuk hindari direktori raksasa
    shard = article_id[:3]
    return root / "html_article" / shard / f"{article_id}.html.gz"


def article_html_relpath(article_id: str) -> str:
    """Path HTML artikel relatif terhadap data/raw/ (untuk tabel mapping).

    Contoh: article_id '8688622' -> 'html_article/868/8688622.html.gz'
    Inilah jembatan eksplisit antara link (url) dan file HTML yang tersimpan.
    """
    shard = article_id[:3]
    return f"html_article/{shard}/{article_id}.html.gz"


def index_html_relpath(day: date, page: int) -> str:
    """Path HTML indeks relatif terhadap data/raw/ (untuk tabel mapping)."""
    return f"html_index/{day:%Y}/{day:%m}/{day:%d}/page_{page}.html.gz"
