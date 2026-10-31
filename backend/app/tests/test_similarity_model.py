"""Evaluation with the real all-MiniLM-L6-v2 model on the labelled sample catalogue.

Skipped if the model cannot be loaded (e.g. offline on the very first run).
Thresholds here come from measured scores (see scripts/evaluate_similarity.py):
true duplicates/variants scored >= 0.96, hard negatives 0.70-0.81, unrelated <= 0.42.
"""
from pathlib import Path

import pandas as pd
import pytest

from app.config import get_settings
from app.intelligence.duplicate_detector import DetectionParams, detect
from app.intelligence.embedding_service import EmbeddingModelError, EmbeddingService
from app.intelligence.evaluation import evaluate, load_labels
from app.services.csv_loader import suggest_mapping

DATA = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture(scope="module")
def real():
    svc = EmbeddingService(get_settings().embedding_model)
    try:
        svc.encode(["warm up"])
    except EmbeddingModelError as exc:
        pytest.skip(f"embedding model unavailable: {exc}")
    df = pd.read_csv(DATA / "similarity_catalogue.csv", dtype=str, keep_default_na=False)
    return svc, df, suggest_mapping(list(df.columns)), load_labels(DATA / "similarity_labels.json")


def run(real, sem):
    svc, df, m, labels = real
    r = detect(df, m, DetectionParams(sem, get_settings().fuzzy_threshold, 5, True), svc, {})
    return evaluate(r.candidates, df, labels)


def test_default_threshold_finds_all_true_pairs_and_no_false_ones(real):
    m = run(real, get_settings().semantic_threshold)
    assert m["duplicates_found"] == "4/4" and m["variants_found"] == "2/2"
    assert m["hard_negatives_flagged"] == [] and m["unrelated_flagged"] == []


def test_looser_threshold_trades_precision_for_the_same_recall(real):
    loose = run(real, 0.70)
    assert loose["recall"] == 1.0
    assert loose["precision"] < run(real, 0.85)["precision"]
    assert len(loose["hard_negatives_flagged"]) > 0  # similar text is not proof of a duplicate
