"""Jalankan crawl L0->L2 untuk Januari 2024 (demonstrasi task 1.5)."""
import sys, yaml
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")
from src.crawl import Crawler, CrawlConfig
from src.pipeline_crawl import run_crawl, build_l1_rules, CrawlPaths

cfg = yaml.safe_load(open("config/config.yaml"))
aliases = yaml.safe_load(open("config/aliases.yaml"))
sel = cfg["selectors"]
l1 = build_l1_rules(aliases)

paths = CrawlPaths(raw=Path("data/raw"), interim=Path("data/interim"))
cc = CrawlConfig(
    user_agent=cfg["crawl"]["user_agent"],
    request_delay_sec=0.5,          # sedikit di bawah 1.0 untuk demo; produksi penuh = 1.0
    jitter_sec=(0.2, 0.6),
)
cw = Crawler(cfg=cc)

print("=== CRAWL Jan 2024 (L0->L2) ===", flush=True)
stats = run_crawl(cw, sel, l1, paths, date(2024, 1, 2), date(2024, 1, 31), seed=cfg["seed"])
print("\n=== SELESAI ===", stats, flush=True)
