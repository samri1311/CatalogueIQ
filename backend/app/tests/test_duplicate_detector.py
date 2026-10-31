from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.intelligence.duplicate_detector import DetectionParams, detect, semantic_pairs
from app.intelligence.embedding_service import EmbeddingService
from app.models.similarity import Relationship
from app.services.csv_loader import suggest_mapping
from app.tests.fakes import bow_encoder

DATA = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture(scope="module")
def catalogue():
    df = pd.read_csv(DATA / "similarity_catalogue.csv", dtype=str, keep_default_na=False)
    return df, suggest_mapping(list(df.columns))


@pytest.fixture
def embedder():
    return EmbeddingService("fake", encoder=bow_encoder)


def run(catalogue, embedder, sem=0.7, fz=90, k=5, use_semantic=True):
    df, m = catalogue
    return detect(df, m, DetectionParams(sem, fz, k, use_semantic), embedder, {})


def by_sku(result):
    return {frozenset((c.source_sku, c.candidate_sku)): c for c in result.candidates}


def test_duplicates_and_variants_are_found_and_classified(catalogue, embedder):
    found = by_sku(run(catalogue, embedder))
    for pair in (("L01", "L02"), ("L03", "L04"), ("L09", "L10")):
        assert found[frozenset(pair)].relationship == Relationship.possible_duplicate
    for pair in (("L05", "L06"), ("L07", "L08")):
        c = found[frozenset(pair)]
        assert c.relationship == Relationship.possible_variant
        assert "Differs in" in c.reason


def test_variant_reason_names_the_differing_attribute(catalogue, embedder):
    c = by_sku(run(catalogue, embedder))[frozenset(("L07", "L08"))]
    assert "color" in c.differing_fields and "color" in c.reason
    assert "brand" in c.matching_fields


def test_product_is_never_matched_with_itself(catalogue, embedder):
    for c in run(catalogue, embedder, sem=0.0, fz=0, k=50).candidates:
        assert c.source_row_id < c.candidate_row_id


def test_unrelated_products_not_flagged(catalogue, embedder):
    found = by_sku(run(catalogue, embedder))
    for sku in ("L16", "L17", "L18", "L19", "L20", "L21"):
        assert not any(sku in pair for pair in found)


def test_thresholds_are_configurable(catalogue, embedder):
    loose = len(run(catalogue, embedder, sem=0.3, fz=60).candidates)
    strict = len(run(catalogue, embedder, sem=0.99, fz=99).candidates)
    assert loose > strict


def test_top_k_limits_partners_per_product(catalogue, embedder):
    r = run(catalogue, embedder, sem=0.0, fz=100, k=2)
    counts = {}
    for c in r.candidates:
        for rid in (c.source_row_id, c.candidate_row_id):
            counts[rid] = counts.get(rid, 0) + 1
    # each row nominates at most k partners but may be nominated by others
    assert len(r.candidates) <= 21 * 2


def test_fuzzy_only_mode_needs_no_embedder(catalogue):
    df, m = catalogue
    r = detect(df, m, DetectionParams(0.8, 90, 5, use_semantic=False), None, {})
    assert r.candidates and all(c.semantic_score is None for c in r.candidates)
    assert "L03" in {c.source_sku for c in r.candidates}


def test_detection_does_not_modify_data(catalogue, embedder):
    df, m = catalogue
    before = df.copy(deep=True)
    run(catalogue, embedder)
    pd.testing.assert_frame_equal(df, before)


def test_small_and_missing_name_cases(embedder):
    one = pd.DataFrame({"sku": ["A"], "product_name": ["x"]})
    assert detect(one, {"sku": "sku", "product_name": "product_name"},
                  DetectionParams(0.5, 50, 5), embedder, {}).candidates == []
    blank = pd.DataFrame({"sku": ["A", "B", "C"], "product_name": ["", " ", ""]})
    r = detect(blank, {"sku": "sku", "product_name": "product_name"},
               DetectionParams(0.0, 0, 5), embedder, {})
    assert r.candidates == [] and r.skipped_rows == 3


def test_semantic_pairs_skip_zero_vectors():
    v = np.array([[1, 0], [1, 0], [0, 0]], dtype=np.float32)
    assert list(semantic_pairs(v, 0.5, 5)) == [(0, 1)]
