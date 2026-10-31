"""Find similar-product candidates for human review.

Retrieval: embeddings (cosine similarity) and RapidFuzz name matching propose
pairs. Deterministic rules then compare attributes and classify each pair.
Similarity only retrieves candidates; it never decides that data is wrong and
nothing is merged or changed here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.intelligence import fuzzy_matcher
from app.intelligence.embedding_service import EmbeddingService, product_text
from app.models.similarity import Relationship, SimilarCandidate
from app.services.normalizer import normalize_key

COMPARE_FIELDS = ["sku", "product_name", "description", "category", "brand",
                  "color", "material", "size", "price", "currency"]
# If any of these differ, similar text most likely describes variants, not duplicates.
HARD_ATTRIBUTES = ["brand", "color", "material", "size"]
CHUNK = 1000


@dataclass(frozen=True)
class DetectionParams:
    semantic_threshold: float
    fuzzy_threshold: float
    top_k: int
    use_semantic: bool = True


@dataclass
class DetectionResult:
    candidates: list[SimilarCandidate]
    compared_rows: int
    skipped_rows: int


def _row_fields(df: pd.DataFrame, mapping: dict[str, str]) -> list[dict[str, str]]:
    cols = {f: mapping[f] for f in COMPARE_FIELDS if f in mapping}
    data = {f: df[c].tolist() for f, c in cols.items()}
    return [{f: data[f][i] for f in data} for i in range(len(df))]


def semantic_pairs(vectors: np.ndarray, threshold: float, top_k: int) -> dict[tuple[int, int], float]:
    """Top-k cosine neighbours per row at or above `threshold`. Zero rows never match."""
    n = len(vectors)
    has_vec = np.linalg.norm(vectors, axis=1) > 0
    pairs: dict[tuple[int, int], float] = {}
    for start in range(0, n, CHUNK):
        sims = vectors[start:start + CHUNK] @ vectors.T  # cosine: vectors are unit length
        for k in range(sims.shape[0]):
            i = start + k
            if not has_vec[i]:
                continue
            row = sims[k]
            row[i] = -1  # never match a product with itself
            row[~has_vec] = -1
            hits = np.flatnonzero(row >= threshold)
            if hits.size > top_k:
                hits = hits[np.argsort(-row[hits], kind="stable")[:top_k]]
            for j in hits:
                a, b = (i, int(j)) if i < j else (int(j), i)
                pairs[(a, b)] = float(row[j])
    return pairs


def _compare(a: dict[str, str], b: dict[str, str]) -> tuple[list[str], list[str]]:
    matching, differing = [], []
    for f in COMPARE_FIELDS:
        if f not in a:
            continue
        va, vb = normalize_key(a[f]), normalize_key(b[f])
        if not va or not vb:
            continue
        (matching if va == vb else differing).append(f)
    return matching, differing


def _reason(sem: float | None, fz: float | None, matching: list[str], differing: list[str],
            relationship: Relationship) -> str:
    scores = []
    if sem is not None:
        scores.append(f"semantic similarity {sem:.2f}")
    if fz is not None:
        scores.append(f"name match {fz:.0f}/100")
    text = "Flagged for " + " and ".join(scores) + "."
    if relationship == Relationship.possible_variant:
        hard = [f for f in differing if f in HARD_ATTRIBUTES]
        text += f" Differs in {', '.join(hard)}, so these may be variants of one product rather than duplicates."
    else:
        text += " No size, colour, material or brand difference was found."
    if "sku" in matching:
        text += " The SKU is identical."
    if "category" in differing:
        text += " The categories differ."
    if "price" in differing:
        text += " The prices differ."
    return text


def detect(df: pd.DataFrame, mapping: dict[str, str], params: DetectionParams,
           embedder: EmbeddingService | None, cache: dict[str, np.ndarray]) -> DetectionResult:
    rows = _row_fields(df, mapping)
    n = len(rows)
    names = [r.get("product_name", "") for r in rows]
    skipped = sum(1 for nm in names if not nm.strip())
    if n < 2 or "product_name" not in mapping:
        return DetectionResult([], n, n if "product_name" not in mapping else skipped)

    pairs: dict[tuple[int, int], dict[str, float | None]] = {}

    vectors = None
    if params.use_semantic:
        if embedder is None:
            raise ValueError("Semantic matching requested without an embedding service.")
        texts = [product_text(r.get("product_name", ""), r.get("category", ""),
                              r.get("brand", ""), r.get("description", "")) if r.get("product_name", "").strip() else ""
                 for r in rows]
        vectors = embedder.embed_with_cache(texts, cache)
        for key, s in semantic_pairs(vectors, params.semantic_threshold, params.top_k).items():
            pairs.setdefault(key, {"sem": None, "fz": None})["sem"] = s

    for key, f in fuzzy_matcher.fuzzy_pairs(names, params.fuzzy_threshold, params.top_k).items():
        pairs.setdefault(key, {"sem": None, "fz": None})["fz"] = f

    candidates = []
    for (i, j), sc in pairs.items():
        sem, fz = sc["sem"], sc["fz"]
        if sem is None and vectors is not None and vectors[i].any() and vectors[j].any():
            sem = float(vectors[i] @ vectors[j])
        if fz is None:
            fz = fuzzy_matcher.score(names[i], names[j])
        matching, differing = _compare(rows[i], rows[j])
        relationship = (Relationship.possible_variant
                        if any(f in HARD_ATTRIBUTES for f in differing)
                        else Relationship.possible_duplicate)
        candidates.append(SimilarCandidate(
            candidate_id=f"{i}-{j}",
            source_row_id=i, candidate_row_id=j,
            source_sku=(rows[i].get("sku") or "").strip() or None,
            candidate_sku=(rows[j].get("sku") or "").strip() or None,
            source_name=names[i], candidate_name=names[j],
            semantic_score=None if sem is None else round(sem, 4),
            fuzzy_score=round(fz, 1),
            matching_fields=matching, differing_fields=differing,
            relationship=relationship,
            reason=_reason(sem, fz, matching, differing, relationship),
        ))

    candidates.sort(key=lambda c: -(c.semantic_score if c.semantic_score is not None
                                    else c.fuzzy_score / 100))
    return DetectionResult(candidates, n, skipped)
