"""
Fase 6 — BERTopic → taksonomi aspek.

Melatih BERTopic HANYA pada kalimat Tier A/B dengan published_at <= cutoff (anti-kebocoran).
Menghasilkan: model, topic_info, metrik (coherence/diversity/outlier), dan template
topic_to_aspect.csv untuk diisi manual.

GPU dipakai otomatis bila torch mendeteksi CUDA.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------- #
# util
# ---------------------------------------------------------------------- #
def detect_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def select_training_corpus(
    sentence_bank: pd.DataFrame,
    cutoff: str = "2024-12-31",
    tiers: tuple[str, ...] = ("A", "B"),
) -> pd.DataFrame:
    """Pilih kalimat UNIK (sentence_id) Tier A/B <= cutoff untuk melatih topik.

    Deduplikasi per sentence_id karena satu kalimat bisa muncul di beberapa bank.
    """
    df = sentence_bank.copy()
    df = df[df["tier"].isin(tiers)]
    pub = pd.to_datetime(df["published_at"], errors="coerce")
    df = df[pub <= pd.Timestamp(cutoff)]
    df = df.drop_duplicates("sentence_id")
    return df[["sentence_id", "text", "published_at", "tier"]].reset_index(drop=True)


# ---------------------------------------------------------------------- #
# konfigurasi BERTopic
# ---------------------------------------------------------------------- #
@dataclass
class TopicConfig:
    embedding_model: str = "intfloat/multilingual-e5-base"
    min_cluster_size: int = 40
    min_samples: int = 10
    n_neighbors: int = 15
    n_components: int = 5
    seed: int = 42
    e5_prefix: str = "query: "          # e5 model card: beri prefix
    stopwords: Optional[list[str]] = None


def build_topic_model(cfg: TopicConfig, device: str = "cpu"):
    """Bangun objek BERTopic (impor di dalam agar modul tetap ringan)."""
    from bertopic import BERTopic
    from bertopic.representation import MaximalMarginalRelevance
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    embedder = SentenceTransformer(cfg.embedding_model, device=device)
    umap_model = UMAP(
        n_neighbors=cfg.n_neighbors,
        n_components=cfg.n_components,
        min_dist=0.0,
        metric="cosine",
        random_state=cfg.seed,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=cfg.min_cluster_size,
        min_samples=cfg.min_samples,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    vectorizer = CountVectorizer(
        ngram_range=(1, 2), min_df=5, stop_words=cfg.stopwords
    )
    topic_model = BERTopic(
        embedding_model=embedder,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        representation_model=MaximalMarginalRelevance(diversity=0.3),
        calculate_probabilities=False,
        verbose=True,
    )
    return topic_model, embedder


def embed_texts(embedder, texts: list[str], cfg: TopicConfig):
    prefixed = [cfg.e5_prefix + t for t in texts]
    return embedder.encode(prefixed, show_progress_bar=True, batch_size=64)


# ---------------------------------------------------------------------- #
# metrik topik
# ---------------------------------------------------------------------- #
def topic_diversity(topic_model, topk: int = 10) -> float:
    """Proporsi kata unik di top-k kata seluruh topik (0-1, makin tinggi makin beragam)."""
    words = []
    for tid in topic_model.get_topics():
        if tid == -1:
            continue
        words += [w for w, _ in topic_model.get_topic(tid)[:topk]]
    return len(set(words)) / max(len(words), 1)


def coherence_cv(topic_model, texts: list[str], topk: int = 10) -> Optional[float]:
    """Coherence c_v via gensim (butuh token). Kembalikan None bila gensim tak ada."""
    try:
        from gensim.corpora import Dictionary
        from gensim.models.coherencemodel import CoherenceModel
    except ImportError:
        return None

    tokenized = [t.lower().split() for t in texts]
    dictionary = Dictionary(tokenized)
    topic_words = []
    for tid in topic_model.get_topics():
        if tid == -1:
            continue
        tw = [w for w, _ in topic_model.get_topic(tid)[:topk] if w]
        if len(tw) >= 2:
            topic_words.append(tw)
    if not topic_words:
        return None
    cm = CoherenceModel(
        topics=topic_words, texts=tokenized, dictionary=dictionary, coherence="c_v"
    )
    return float(cm.get_coherence())


# ---------------------------------------------------------------------- #
# template pemetaan topik -> aspek (diisi manual)
# ---------------------------------------------------------------------- #
ASPECTS = {
    "A1": "Kinerja keuangan",
    "A2": "Kualitas aset & risiko kredit",
    "A3": "Aksi korporasi & dividen",
    "A4": "Penyaluran kredit & ekspansi",
    "A5": "Kebijakan & regulasi",
    "A6": "Digital & operasional",
    "A7": "Pandangan analis & valuasi",
    "A8": "Tata kelola, hukum & reputasi",
    "S1": "Market wrap & arus transaksi",
    "S2": "Makro & umum",
    "S3": "Lainnya (dibuang)",
}


def make_topic_aspect_template(topic_model) -> pd.DataFrame:
    info = topic_model.get_topic_info()  # Topic, Count, Name, Representation...
    rows = []
    for _, r in info.iterrows():
        tid = r["Topic"]
        if tid == -1:
            keywords = "(outlier)"
        else:
            keywords = ", ".join(w for w, _ in topic_model.get_topic(tid)[:10])
        rows.append(
            {
                "topic_id": tid,
                "count": r["Count"],
                "keywords": keywords,
                "aspect_annotator_1": "",  # diisi manual (kode A1-A8/S1-S3)
                "aspect_annotator_2": "",  # diisi manual oleh orang kedua
                "aspect_final": "",         # hasil rekonsiliasi
            }
        )
    return pd.DataFrame(rows)
