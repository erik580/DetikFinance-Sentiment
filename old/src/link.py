"""
Fase 5b — Entity linking kalimat -> bank.

link_type:
  explicit  : kalimat menyebut alias bank langsung
  inherited : kalimat anaforik (perseroan/bank tersebut/emiten) DAN artikel hanya 1 bank
  group     : sebutan grup (Himbara/bank BUMN) -> BBRI, BBNI, BMRI (weight 0.5)

Aturan:
  - kalimat 2 bank -> 2 baris (sentimen dinilai per bank)
  - anafora di artikel multi-bank -> ambigu -> dibuang
  - anak usaha di-mask agar tidak dihitung bank induk
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

GROUP_BANKS = ("BBRI", "BBNI", "BMRI")
GROUP_WEIGHT = 0.5
FULL_WEIGHT = 1.0

# kata anaforik yang mengacu ke bank utama artikel
_ANAPHORA_RX = re.compile(
    r"\b(perseroan|perusahaan|bank tersebut|bank ini|emiten|manajemen)\b", re.IGNORECASE
)


@dataclass
class LinkRules:
    bank_rx: dict[str, re.Pattern]
    subsidiary_rx: Optional[re.Pattern]
    group_rx: re.Pattern


def build_link_rules(aliases: dict) -> LinkRules:
    bank_rx = {
        b: re.compile("|".join(pats), re.IGNORECASE) for b, pats in aliases["banks"].items()
    }
    subs = aliases.get("subsidiaries", [])
    sub_rx = re.compile("|".join(subs), re.IGNORECASE) if subs else None
    grp = re.compile("|".join(aliases.get("group", [])), re.IGNORECASE)
    return LinkRules(bank_rx=bank_rx, subsidiary_rx=sub_rx, group_rx=grp)


def _mask_sub(text: str, sub_rx: Optional[re.Pattern]) -> str:
    return sub_rx.sub(" <SUB> ", text) if sub_rx else text


def banks_in_text(text: str, rules: LinkRules) -> list[str]:
    masked = _mask_sub(text, rules.subsidiary_rx)
    return [b for b, rx in rules.bank_rx.items() if rx.search(masked)]


def article_banks(article_text: str, rules: LinkRules) -> list[str]:
    """Bank-bank yang muncul di seluruh artikel (untuk tentukan artikel 1-bank)."""
    return banks_in_text(article_text, rules)


def link_sentence(
    sentence: str,
    rules: LinkRules,
    article_bank_set: list[str],
) -> list[dict]:
    """Kembalikan daftar tautan {bank, link_type, weight} untuk satu kalimat."""
    masked = _mask_sub(sentence, rules.subsidiary_rx)
    links: list[dict] = []

    # 1. explicit — alias bank langsung
    explicit = [b for b, rx in rules.bank_rx.items() if rx.search(masked)]
    for b in explicit:
        links.append({"bank": b, "link_type": "explicit", "weight": FULL_WEIGHT})

    # 2. group — Himbara/bank BUMN.
    #    HANYA bila kalimat TIDAK menyebut bank tertentu secara eksplisit.
    #    Alasan: kalau kalimat sudah spesifik (mis. "BRI berkomitmen..."), kalimat itu
    #    tentang bank itu, BUKAN tentang "grup" — jadi jangan fan-out ke bank BUMN lain
    #    (ini sumber salah-tag bank, mis. kalimat BRI dapat tag BMRI).
    if not explicit and rules.group_rx.search(masked):
        for b in GROUP_BANKS:
            links.append({"bank": b, "link_type": "group", "weight": GROUP_WEIGHT})

    # 3. inherited — anafora, hanya bila artikel 1 bank & kalimat belum punya explicit
    if not explicit and _ANAPHORA_RX.search(sentence):
        if len(article_bank_set) == 1:
            links.append(
                {"bank": article_bank_set[0], "link_type": "inherited", "weight": FULL_WEIGHT}
            )
        # artikel multi-bank -> ambigu -> dibuang (tidak di-emit)

    return links
