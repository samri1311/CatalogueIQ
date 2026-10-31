"""Score similarity candidates against a labelled catalogue.

Labelled pairs are expected to fall in one of these groups:
  duplicate      -> should be flagged as possible_duplicate
  variant        -> should be flagged as possible_variant
  hard_negative  -> similar-looking but different products; should NOT be flagged
Every other pair in the catalogue is treated as unrelated (should not be flagged).
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from app.models.similarity import Relationship, SimilarCandidate

Pair = frozenset


def load_labels(path: Path) -> dict[str, set[Pair]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: {frozenset(p) for p in v} for k, v in raw.items()}


def evaluate(candidates: list[SimilarCandidate], df: pd.DataFrame,
             labels: dict[str, set[Pair]]) -> dict:
    sku = df["sku"].tolist()
    flagged = {frozenset((c.source_sku, c.candidate_sku)): c for c in candidates}
    labelled = set().union(*labels.values())
    all_pairs = {frozenset(p) for p in itertools.combinations(sku, 2)}
    unrelated = all_pairs - labelled

    dup_found = [p for p in labels["duplicate"] if p in flagged
                 and flagged[p].relationship == Relationship.possible_duplicate]
    var_found = [p for p in labels["variant"] if p in flagged
                 and flagged[p].relationship == Relationship.possible_variant]
    neg_flagged = [p for p in labels["hard_negative"] if p in flagged]
    unrelated_flagged = [p for p in unrelated if p in flagged]

    true_pos = len(dup_found) + len(var_found)
    expected = len(labels["duplicate"]) + len(labels["variant"])
    false_pos = len(neg_flagged) + len(unrelated_flagged)
    return {
        "duplicates_found": f"{len(dup_found)}/{len(labels['duplicate'])}",
        "variants_found": f"{len(var_found)}/{len(labels['variant'])}",
        "hard_negatives_flagged": sorted(tuple(sorted(p)) for p in neg_flagged),
        "unrelated_flagged": sorted(tuple(sorted(p)) for p in unrelated_flagged),
        "recall": true_pos / expected if expected else 1.0,
        "precision": true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 1.0,
        "flagged_total": len(flagged),
    }


def score_table(candidates: list[SimilarCandidate], labels: dict[str, set[Pair]]) -> list[tuple]:
    by_pair = {frozenset((c.source_sku, c.candidate_sku)): c for c in candidates}
    rows = []
    for group, pairs in labels.items():
        for p in sorted(tuple(sorted(x)) for x in pairs):
            c = by_pair.get(frozenset(p))
            rows.append((group, *p, c.semantic_score if c else None,
                         c.fuzzy_score if c else None, c.relationship.value if c else "not flagged"))
    return rows
