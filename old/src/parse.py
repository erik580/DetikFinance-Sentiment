"""
Parsing HTML indeks & artikel DetikFinance menjadi record terstruktur.

Semua selektor dibaca dari config agar mudah diperbaiki per era HTML.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .crawl import article_id_from_url

# subchannel = segmen path pertama pada URL artikel detikFinance
_SUBCHANNEL_RE = re.compile(r"finance\.detik\.com/([a-z0-9-]+)/d-\d+")


def subchannel_from_url(url: str) -> Optional[str]:
    m = _SUBCHANNEL_RE.search(url)
    return m.group(1) if m else None


@dataclass
class IndexItem:
    url: str
    article_id: str
    title: str
    subchannel: Optional[str]
    date_text: Optional[str]  # teks tanggal mentah dari indeks (jam terbit resmi diambil dari artikel)


def parse_index(html: str, selectors: dict) -> list[IndexItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[IndexItem] = []
    seen: set[str] = set()
    for node in soup.select(selectors["index_item"]):
        a = node.select_one(selectors["index_link"]) or node.select_one("a")
        if not a or not a.has_attr("href"):
            continue
        url = a["href"].split("?")[0].strip()
        if not re.search(r"/d-\d+/", url):
            continue
        if url in seen:
            continue
        seen.add(url)

        title_node = node.select_one(selectors["index_title"])
        date_node = node.select_one(selectors["index_date"])
        items.append(
            IndexItem(
                url=url,
                article_id=article_id_from_url(url),
                title=title_node.get_text(strip=True) if title_node else "",
                subchannel=subchannel_from_url(url),
                date_text=date_node.get_text(" ", strip=True) if date_node else None,
            )
        )
    return items


@dataclass
class Article:
    article_id: str
    url: str
    title: str
    published_at: Optional[str]  # ISO string WIB
    subchannel: Optional[str]
    body_text: str
    n_words: int


def _parse_published(soup: BeautifulSoup, selectors: dict) -> Optional[str]:
    meta = soup.select_one(selectors["article_published_meta"])
    if meta and meta.has_attr("content"):
        raw = meta["content"].strip()  # "YYYY/MM/DD HH:MM:SS"
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt).isoformat()
            except ValueError:
                continue
    return None


def parse_article(html: str, url: str, selectors: dict) -> Article:
    soup = BeautifulSoup(html, "lxml")

    title_node = soup.select_one(selectors["article_title"])
    title = title_node.get_text(strip=True) if title_node else ""

    body = soup.select_one(selectors["article_body"])
    text = ""
    if body:
        for sel in selectors.get("article_body_junk", []):
            for junk in body.select(sel):
                junk.decompose()
        paras = [p.get_text(" ", strip=True) for p in body.select("p")]
        text = " ".join(p for p in paras if p)

    return Article(
        article_id=article_id_from_url(url),
        url=url,
        title=title,
        published_at=_parse_published(soup, selectors),
        subchannel=subchannel_from_url(url),
        body_text=text,
        n_words=len(text.split()),
    )
