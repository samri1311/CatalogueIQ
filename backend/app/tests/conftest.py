from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import store
from app.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "synthetic_catalogue.csv"


@pytest.fixture
def sample_bytes() -> bytes:
    return SAMPLE.read_bytes()


@pytest.fixture
def client():
    store.clear()
    yield TestClient(app)
    store.clear()


@pytest.fixture
def uploaded(client, sample_bytes):
    r = client.post("/api/upload", files={"file": ("cat.csv", sample_bytes, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()
