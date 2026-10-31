"""Evaluate similarity matching on the labelled sample catalogue.

Run from backend/:  .\.venv\Scripts\python.exe -m scripts.evaluate_similarity
The first run downloads the embedding model (internet needed); later runs use the cache.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.intelligence.duplicate_detector import DetectionParams, detect
from app.intelligence.embedding_service import EmbeddingService
from app.intelligence.evaluation import evaluate, load_labels, score_table
from app.services.csv_loader import suggest_mapping

DATA = Path(__file__).resolve().parents[1] / "sample_data"


def main() -> None:
    s = get_settings()
    df = pd.read_csv(DATA / "similarity_catalogue.csv", dtype=str, keep_default_na=False)
    mapping = suggest_mapping(list(df.columns))
    labels = load_labels(DATA / "similarity_labels.json")
    embedder = EmbeddingService(s.embedding_model)
    cache: dict = {}

    # 1) Raw scores for every labelled pair (thresholds at 0 flag everything).
    everything = detect(df, mapping, DetectionParams(0.0, 0.0, 1000, True), embedder, cache)
    print(f"{'group':14} {'a':4} {'b':4} {'semantic':>9} {'fuzzy':>7}  relationship")
    for g, a, b, sem, fz, rel in score_table(everything.candidates, labels):
        print(f"{g:14} {a:4} {b:4} {sem!s:>9} {fz!s:>7}  {rel}")

    unlabelled = [c for c in everything.candidates
                  if frozenset((c.source_sku, c.candidate_sku)) not in set().union(*labels.values())]
    top = sorted(unlabelled, key=lambda c: -c.semantic_score)[:5]
    print("\nHighest-scoring unrelated pairs:")
    for c in top:
        print(f"  {c.source_sku}-{c.candidate_sku} semantic={c.semantic_score} fuzzy={c.fuzzy_score}"
              f"  ({c.source_name} / {c.candidate_name})")

    # 2) Quality at a grid of thresholds.
    print("\nthreshold grid (fuzzy threshold fixed at default):")
    for t in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
        r = detect(df, mapping, DetectionParams(t, s.fuzzy_threshold, s.similarity_top_k, True), embedder, cache)
        m = evaluate(r.candidates, df, labels)
        print(f"  semantic>={t:.2f}  dup {m['duplicates_found']}  var {m['variants_found']}  "
              f"precision {m['precision']:.2f}  recall {m['recall']:.2f}  flagged {m['flagged_total']}")


if __name__ == "__main__":
    main()
