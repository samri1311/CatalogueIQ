from pathlib import Path

import pytest

from app.deps import get_embedder, settings, store
from app.intelligence.embedding_service import EmbeddingModelError, EmbeddingService
from app.main import app
from app.tests.fakes import bow_encoder

DATA = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture
def sim(client):
    app.dependency_overrides[get_embedder] = lambda: EmbeddingService("fake", encoder=bow_encoder)
    r = client.post("/api/upload", files={"file": ("s.csv", (DATA / "similarity_catalogue.csv").read_bytes(), "text/csv")})
    cid = r.json()["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")
    yield cid
    app.dependency_overrides.pop(get_embedder, None)


def get(client, cid, **params):
    return client.get(f"/api/catalogue/{cid}/similar-products", params={"semantic_threshold": 0.7, **params})


def test_returns_structured_candidates(client, sim):
    r = get(client, sim)
    assert r.status_code == 200
    body = r.json()
    assert body["compared_rows"] == 21 and body["model"] == "fake"
    c = next(c for c in body["candidates"] if {c["source_sku"], c["candidate_sku"]} == {"L01", "L02"})
    for key in ("source_row_id", "candidate_row_id", "semantic_score", "fuzzy_score",
                "matching_fields", "reason", "review_status", "relationship"):
        assert key in c
    assert c["review_status"] == "pending"


def test_review_status_persists_and_never_changes_data(client, sim):
    before = store.get(sim).working.copy(deep=True)
    c = next(c for c in get(client, sim).json()["candidates"] if c["relationship"] == "possible_duplicate")
    r = client.post(f"/api/catalogue/{sim}/similar-products/{c['candidate_id']}/review",
                    json={"status": "not_duplicate"})
    assert r.status_code == 200
    again = {x["candidate_id"]: x for x in get(client, sim).json()["candidates"]}
    assert again[c["candidate_id"]]["review_status"] == "not_duplicate"
    assert store.get(sim).working.equals(before)
    assert store.get(sim).original.equals(before)


def test_unknown_candidate_and_bad_status(client, sim):
    get(client, sim)
    assert client.post(f"/api/catalogue/{sim}/similar-products/99-100/review",
                       json={"status": "duplicate"}).status_code == 404
    assert client.post(f"/api/catalogue/{sim}/similar-products/0-1/review",
                       json={"status": "merge"}).status_code == 422


def test_summary_reports_potential_duplicates_after_run(client, sim):
    assert client.get(f"/api/catalogue/{sim}/summary").json()["potential_duplicates"] is None
    get(client, sim)
    n = client.get(f"/api/catalogue/{sim}/summary").json()["potential_duplicates"]
    assert isinstance(n, int) and n >= 3


def test_fuzzy_only_mode(client, sim):
    body = get(client, sim, semantic=False).json()
    assert body["model"] is None and body["params"]["semantic_enabled"] is False
    assert body["candidates"] and all(c["semantic_score"] is None for c in body["candidates"])


def test_threshold_validation(client, sim):
    assert get(client, sim, semantic_threshold=1.5).status_code == 422
    assert get(client, sim, fuzzy_threshold=-1).status_code == 422


def test_model_failure_is_503_with_message(client, sim):
    class Broken(EmbeddingService):
        def encode(self, texts):
            raise EmbeddingModelError("Could not load embedding model: offline")

    app.dependency_overrides[get_embedder] = lambda: Broken("m")
    r = get(client, sim)
    assert r.status_code == 503 and "offline" in r.json()["detail"]
    assert get(client, sim, semantic=False).status_code == 200  # fuzzy-only still works


def test_row_limit(client, sim):
    object.__setattr__(settings, "max_similarity_rows", 5)
    try:
        assert get(client, sim).status_code == 413
    finally:
        object.__setattr__(settings, "max_similarity_rows", 5000)


def test_requires_product_name_mapping(client, sim):
    client.post(f"/api/catalogue/{sim}/analyze", json={"mapping": {"sku": "sku"}})
    assert get(client, sim).status_code == 409


def test_uses_working_copy_after_corrections(client, sim):
    # Editing a name through the review workflow changes what similarity sees.
    cat = store.get(sim)
    cat.working.at[1, "product_name"] = "Completely Different Garden Gnome"
    cands = get(client, sim).json()["candidates"]
    names = {c["candidate_name"] for c in cands} | {c["source_name"] for c in cands}
    assert "Completely Different Garden Gnome" in names  # the edited working value is used
    assert "Classic Cotton Tshirt" not in names
    assert store.get(sim).original.at[1, "product_name"] == "Classic Cotton Tshirt"
