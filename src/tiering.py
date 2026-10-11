"""
Fase 4 — Tiering relevansi per bank.

Input : news_clean.parquet (artikel bersih, Fase 3)
Output: news_tiered.parquet — satu baris per (article_id, bank) dengan tier & skor.

Skor relevansi (spec §5.3):
    s_b = 3*[bank di judul] + 2*[bank di 3 kalimat awal] + min(n_sebut_badan, 3)

Tier:
    A : s_b >= 3                              (spesifik bank; weight 1.0)
    B : tak ada bank Tier A, TAPI ada grup    (Himbara/bank BUMN/perbankan) atau
        regulasi (OJK/BI/LPS) di judul/awal    (sektor; weight 0.5 untuk bank BUMN)
    C : judul/subchannel pasar-makro          (IHSG/rupiah/inflasi/bursa; konteks)
    D : selain itu                            (dibuang)

Catatan:
- Anak usaha (Mandiri Sekuritas, BNI Sekuritas, dll) di-MASK dulu sebelum menghitung
  sebutan bank induk, agar tidak salah hitung.
- "Mandiri" sendirian dihitung BMRI; "Mandiri Sekuritas" dst sudah ter-mask.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

# bank BUMN yang mewarisi sentimen grup (Himbara) — BBCA swasta, tidak termasuk
GROUP_BANKS = ("BBRI", "BBNI", "BMRI")
GROUP_WEIGHT = 0.5
FULL_WEIGHT = 1.0


@dataclass
class TierRules:
    bank_rx: dict[str, re.Pattern]
    subsidiary_rx: Optional[re.Pattern]
    group_rx: re.Pattern
    policy_rx: re.Pattern
    market_rx: re.Pattern
    market_subchannels: tuple[str, ...] = ("bursa-dan-valas", "market-research")


def build_tier_rules(aliases: dict) -> TierRules:
    bank_rx = {
        b: re.compile("|".join(pats), re.IGNORECASE) for b, pats in aliases["banks"].items()
    }
    subs = aliases.get("subsidiaries", [])
    sub_rx = re.compile("|".join(subs), re.IGNORECASE) if subs else None
    return TierRules(
        bank_rx=bank_rx,
        subsidiary_rx=sub_rx,
        group_rx=re.compile("|".join(aliases.get("group", [])), re.IGNORECASE),
        policy_rx=re.compile("|".join(aliases.get("policy_keywords", [])), re.IGNORECASE),
        market_rx=re.compile("|".join(aliases.get("market_keywords", [])), re.IGNORECASE),
    )


# segmentasi kalimat sederhana untuk mengambil "3 kalimat pertama"
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _first_sentences(text: str, n: int = 3) -> str:
    parts = _SENT_SPLIT.split(text.strip())
    return " ".join(parts[:n])


def _mask_subsidiaries(text: str, sub_rx: Optional[re.Pattern]) -> str:
    if sub_rx is None:
        return text
    return sub_rx.sub(" <SUB> ", text)


def _bank_score(title: str, body: str, rx: re.Pattern) -> tuple[int, int, int, int]:
    """Kembalikan (skor, in_title, in_lead, n_body_capped)."""
    in_title = 1 if rx.search(title) else 0
    lead = _first_sentences(body, 3)
    in_lead = 1 if rx.search(lead) else 0
    n_body = len(rx.findall(body))
    n_capped = min(n_body, 3)
    score = 3 * in_title + 2 * in_lead + n_capped
    return score, in_title, in_lead, n_capped


def tier_articles(df: pd.DataFrame, rules: TierRules) -> pd.DataFrame:
    """Hasilkan tabel panjang (article_id, bank, tier, score, weight, ...)."""
    rows: list[dict] = []

    for _, art in df.iterrows():
        title = art.get("title", "") or ""
        body_raw = art.get("body_text", "") or ""
        body = _mask_subsidiaries(body_raw, rules.subsidiary_rx)
        title_m = _mask_subsidiaries(title, rules.subsidiary_rx)

        # skor tiap bank
        bank_scores = {}
        for bank, rx in rules.bank_rx.items():
            s, it, il, nb = _bank_score(title_m, body, rx)
            bank_scores[bank] = (s, it, il, nb)

        any_tier_a = any(s >= 3 for s, *_ in bank_scores.values())

        # sinyal sektor/grup & pasar (dari judul + 3 kalimat awal)
        head = f"{title} {_first_sentences(body_raw, 3)}"
        has_group = bool(rules.group_rx.search(head))
        has_policy = bool(rules.policy_rx.search(head))
        has_market = bool(rules.market_rx.search(head)) or (
            art.get("subchannel") in rules.market_subchannels
        )

        emitted = False
        for bank, (s, it, il, nb) in bank_scores.items():
            if s >= 3:
                rows.append(_row(art, bank, "A", s, FULL_WEIGHT, it, il, nb))
                emitted = True

        # Tier B: tidak ada bank Tier A untuk artikel ini, tapi ada sinyal grup/regulasi
        if not any_tier_a and (has_group or has_policy):
            if has_group:
                # grup Himbara → tautkan ke bank BUMN dengan bobot 0.5
                for bank in GROUP_BANKS:
                    rows.append(_row(art, bank, "B", bank_scores[bank][0], GROUP_WEIGHT, 0, 0, 0))
                emitted = True
            else:
                # regulasi tanpa grup → tautkan ke bank yang (lemah) tersebut, else semua target
                mentioned = [b for b, (s, *_ ) in bank_scores.items() if s > 0]
                targets = mentioned if mentioned else list(rules.bank_rx.keys())
                for bank in targets:
                    rows.append(_row(art, bank, "B", bank_scores[bank][0], GROUP_WEIGHT, 0, 0, 0))
                emitted = True

        # Tier C: artikel pasar/makro (konteks) — satu baris, bank = None
        if not emitted and has_market:
            rows.append(_row(art, None, "C", 0, 0.0, 0, 0, 0))
            emitted = True

        # Tier D: tidak relevan → tidak di-emit (dibuang)

    return pd.DataFrame(rows)


def _row(art, bank, tier, score, weight, it, il, nb) -> dict:
    return {
        "article_id": art["article_id"],
        "bank": bank,
        "tier": tier,
        "relevance_score": score,
        "weight": weight,
        "in_title": it,
        "in_lead": il,
        "n_body": nb,
        "published_at": art.get("published_at"),
        "subchannel": art.get("subchannel"),
        "title": art.get("title"),
    }
