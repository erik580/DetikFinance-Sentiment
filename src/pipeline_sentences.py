"""
Fase 5 — pipeline: artikel Tier A/B/C -> sentences + sentence_bank.

Menghasilkan 2 tabel:
  sentences      : sentence_id, article_id, sent_idx, text_raw, text_k, n_tokens
  sentence_bank  : sentence_id, bank, link_type, weight, text, published_at, tier
"""
from __future__ import annotations

import pandas as pd
from tqdm import tqdm

from .link import LinkRules, article_banks, link_sentence
from .segment import preprocess_track_k, preprocess_track_t, split_sentences


def build_sentences(
    tiered: pd.DataFrame,
    clean: pd.DataFrame,
    rules: LinkRules,
    do_stem: bool = True,
    min_tokens: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    tiered: tabel (article_id, bank, tier, ...) dari Fase 4
    clean : tabel artikel bersih (article_id, body_text, published_at, ...) dari Fase 3
    """
    # artikel yang masuk (Tier A/B/C) — ambil unik + info tier terbaik
    keep_ids = tiered["article_id"].unique()
    body_map = clean.set_index("article_id")[["body_text", "published_at"]].to_dict("index")
    # tier representatif per artikel (A > B > C) untuk kolom konteks
    tier_order = {"A": 0, "B": 1, "C": 2}
    best_tier = (
        tiered.assign(_o=tiered["tier"].map(tier_order))
        .sort_values("_o")
        .drop_duplicates("article_id")
        .set_index("article_id")["tier"]
        .to_dict()
    )

    sent_rows: list[dict] = []
    link_rows: list[dict] = []

    for aid in tqdm(keep_ids, desc="segmentasi+linking"):
        info = body_map.get(aid)
        if not info:
            continue
        body = info["body_text"] or ""
        pub = info["published_at"]
        tier = best_tier.get(aid)

        sentences = split_sentences(body, min_tokens=min_tokens)
        if not sentences:
            continue

        art_banks = article_banks(body, rules)  # untuk aturan inherited

        for idx, sent in enumerate(sentences):
            sid = f"{aid}_{idx}"
            text_t = preprocess_track_t(sent)
            text_k = preprocess_track_k(sent, do_stem=do_stem)
            sent_rows.append(
                {
                    "sentence_id": sid,
                    "article_id": aid,
                    "sent_idx": idx,
                    "text_raw": text_t,
                    "text_k": text_k,
                    "n_tokens": len(sent.split()),
                }
            )
            for link in link_sentence(sent, rules, art_banks):
                link_rows.append(
                    {
                        "sentence_id": sid,
                        "article_id": aid,
                        "bank": link["bank"],
                        "link_type": link["link_type"],
                        "weight": link["weight"],
                        "text": text_t,
                        "published_at": pub,
                        "tier": tier,
                    }
                )

    sentences = pd.DataFrame(sent_rows)
    sentence_bank = pd.DataFrame(link_rows)
    return sentences, sentence_bank
