"""RapidFuzz name matching.

Finds near-identical titles (typos, punctuation, word order). A high score is
a reason to look at a pair, never proof that two products are duplicates.
"""
from __future__ import annotations

import re

import numpy as np
from rapidfuzz import fuzz, process

_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", title.casefold())).strip()


def score(a: str, b: str) -> float:
    """Token-sort ratio (0-100) of two raw titles; word order does not matter."""
    return float(fuzz.token_sort_ratio(normalize_title(a), normalize_title(b)))


def fuzzy_pairs(titles: list[str], threshold: float, top_k: int) -> dict[tuple[int, int], float]:
    """Return {(i, j): score} with i < j for pairs scoring >= threshold.

    Each title keeps at most `top_k` partners, so a block of identical titles
    cannot explode into every possible pair. Blank titles never match.
    """
    n = len(titles)
    if n < 2:
        return {}
    norm = [normalize_title(t) for t in titles]
    valid = np.array([bool(t) for t in norm])
    scores = process.cdist(norm, norm, scorer=fuzz.token_sort_ratio, dtype=np.float32, workers=-1)
    scores[~valid, :] = -1
    scores[:, ~valid] = -1
    np.fill_diagonal(scores, -1)

    pairs: dict[tuple[int, int], float] = {}
    for i in range(n):
        row = scores[i]
        hits = np.flatnonzero(row >= threshold)
        if hits.size == 0:
            continue
        if hits.size > top_k:
            hits = hits[np.argsort(-row[hits], kind="stable")[:top_k]]
        for j in hits:
            a, b = (i, int(j)) if i < j else (int(j), i)
            pairs[(a, b)] = float(row[j])
    return pairs
