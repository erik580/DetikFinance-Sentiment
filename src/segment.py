"""
Fase 5a — Segmentasi kalimat + dua preprocessing track.

- Segmentasi: regex + daftar singkatan Indonesia terlindungi (agar "Tbk.", "Rp",
  "PT.", "yoy.", "No.7" tidak salah dipecah).
- Track T (transformer): nyaris mentah (pertahankan huruf besar, angka, %, Rp).
- Track K (klasik): lowercase, buang tanda baca, angka->token, stopword, stemming Sastrawi.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

# ---------------------------------------------------------------------- #
# Segmentasi kalimat
# ---------------------------------------------------------------------- #
# Singkatan yang TIDAK boleh memicu akhir kalimat (titik di belakangnya dilindungi).
PROTECTED_ABBREV = [
    "Tbk", "PT", "CV", "Rp", "No", "dll", "dsb", "dst", "yoy", "mtm", "qoq",
    "dr", "Dr", "Ir", "H", "Hj", "Bpk", "Prof", "a.n", "u.p", "d.a",
    "Jl", "Kec", "Kel", "Kab", "Prov", "Rt", "Rw", "Tn", "Ny", "Sdr",
    "approx", "etc", "Inc", "Ltd", "Jr", "Sr", "M.M", "S.E", "S.H",
]

# tandai titik pada singkatan supaya tidak dipakai sebagai pemisah
_ABBREV_RX = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in PROTECTED_ABBREV) + r")\.", re.IGNORECASE
)
# titik di antara angka (desimal/ribuan): 7.323,5 atau No.7
_NUM_DOT_RX = re.compile(r"(?<=\d)\.(?=\d)")
_PLACEHOLDER = "\u2063"  # invisible separator sebagai pengganti titik sementara

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def split_sentences(text: str, min_tokens: int = 5) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    # lindungi titik pada singkatan & angka
    protected = _ABBREV_RX.sub(lambda m: m.group(0).replace(".", _PLACEHOLDER), text)
    protected = _NUM_DOT_RX.sub(_PLACEHOLDER, protected)

    parts = _SENT_BOUNDARY.split(protected)
    out: list[str] = []
    for p in parts:
        s = p.replace(_PLACEHOLDER, ".").strip()
        if len(s.split()) >= min_tokens:
            out.append(s)
    return out


# ---------------------------------------------------------------------- #
# Track T (transformer) — minimal
# ---------------------------------------------------------------------- #
def preprocess_track_t(sentence: str) -> str:
    s = re.sub(r"\s+", " ", sentence).strip()
    return s


# ---------------------------------------------------------------------- #
# Track K (klasik) — untuk LDA/NMF/TF-IDF
# ---------------------------------------------------------------------- #
_RP_RX = re.compile(r"\bRp\s?\d[\d.,]*", re.IGNORECASE)
_NUM_RX = re.compile(r"\b\d[\d.,]*\b")
_PUNCT_RX = re.compile(r"[^\w\s]")

# stopword domain tambahan (di luar daftar Sastrawi)
DOMAIN_STOPWORDS = {
    "detikcom", "detikfinance", "jakarta", "persen", "rp", "num",
    "foto", "video", "baca", "simak", "lihat", "halaman",
}


@lru_cache(maxsize=1)
def _get_sastrawi():
    """Muat stemmer & stopword Sastrawi sekali (lambat, jadi di-cache)."""
    try:
        from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
        from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    except ImportError:
        return None, set()
    stemmer = StemmerFactory().create_stemmer()
    stopwords = set(StopWordRemoverFactory().get_stop_words()) | DOMAIN_STOPWORDS
    return stemmer, stopwords


@lru_cache(maxsize=100_000)
def _stem_word(word: str) -> str:
    stemmer, _ = _get_sastrawi()
    if stemmer is None:
        return word
    return stemmer.stem(word)


def preprocess_track_k(sentence: str, do_stem: bool = True) -> str:
    _, stopwords = _get_sastrawi()
    s = sentence
    s = _RP_RX.sub(" <RP> ", s)
    s = s.lower()
    s = _NUM_RX.sub(" <NUM> ", s)
    s = _PUNCT_RX.sub(" ", s.replace("<rp>", "<RP>").replace("<num>", "<NUM>"))
    tokens = []
    for tok in s.split():
        if tok in ("<RP>", "<NUM>"):
            tokens.append(tok)
            continue
        if tok in stopwords or len(tok) < 2:
            continue
        tokens.append(_stem_word(tok) if do_stem else tok)
    return " ".join(tokens)
