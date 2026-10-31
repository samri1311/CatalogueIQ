import logging
import os
import tempfile

import pandas as pd
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.deps import store
from app.main import BodyLimitMiddleware
from app.services.catalogue_store import CatalogueStore


def test_body_limit_rejects_by_content_length_and_streamed_bodies():
    tiny = FastAPI()
    tiny.add_middleware(BodyLimitMiddleware, max_bytes=1000)

    @tiny.post("/echo")
    async def echo(request: Request):
        return {"n": len(await request.body())}

    c = TestClient(tiny)
    assert c.post("/echo", content=b"x" * 500).json() == {"n": 500}
    big = c.post("/echo", content=b"x" * 5000)
    assert big.status_code == 413 and "too large" in big.json()["detail"]

    def chunks():  # no Content-Length header: must still be stopped
        for _ in range(10):
            yield b"y" * 500

    assert c.post("/echo", content=chunks()).status_code == 413


def test_oversized_file_rejected_by_api(client):
    r = client.post("/api/upload", files={"file": ("big.csv", b"a\n" + b"1\n" * 50, "text/csv")})
    assert r.status_code == 200  # sanity: small file ok
    from app.deps import settings
    object.__setattr__(settings, "max_rows", 10)
    try:
        r = client.post("/api/upload", files={"file": ("big.csv", b"a\n" + b"1\n" * 50, "text/csv")})
        assert r.status_code == 400 and "rows" in r.json()["detail"]
    finally:
        object.__setattr__(settings, "max_rows", 50_000)


def test_binary_and_wrong_type_uploads_rejected(client):
    assert client.post("/api/upload", files={"file": ("a.csv", b"\x89PNG\r\n\x00\x00", "text/csv")}).status_code == 400
    assert client.post("/api/upload", files={"file": ("a.exe", b"a,b\n1,2\n", "text/csv")}).status_code == 400
    assert client.post("/api/upload", files={"file": ("a.csv", b"", "text/csv")}).status_code == 400


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "cache-control" not in r.headers
    assert client.get("/api/catalogue/nope").headers["cache-control"] == "no-store"


def test_cors_allows_only_the_dev_frontend(client):
    ok = client.options("/api/upload", headers={"Origin": "http://localhost:5173",
                                                "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/upload", headers={"Origin": "http://evil.example",
                                                 "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_large_upload_leaves_no_temp_files_behind(client):
    tmp = tempfile.gettempdir()
    before = set(os.listdir(tmp))
    body = "sku,product_name,price\n" + "".join(f"S{i},Product {i} with a long name,9.99\n" for i in range(45_000))
    assert len(body) > 1_500_000  # well past Starlette's 1 MB in-memory spool limit
    r = client.post("/api/upload", files={"file": ("big.csv", body.encode(), "text/csv")})
    assert r.status_code == 200
    assert set(os.listdir(tmp)) - before == set()


def test_no_catalogue_contents_are_logged(client, uploaded, caplog):
    caplog.set_level(logging.DEBUG)
    cid = uploaded["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")
    i = client.get(f"/api/catalogue/{cid}/issues", params={"row_id": 5, "issue_type": "whitespace"}).json()["issues"][0]
    client.post(f"/api/issues/{i['issue_id']}/review", json={"action": "accept"})
    client.get(f"/api/catalogue/{cid}/export")
    client.get(f"/api/catalogue/{cid}/report")
    logged = " ".join(r.getMessage() for r in caplog.records)
    for secret in ("Stainless Water Bottle", "HydroMax", "SKU-006", "Fragile", "Aisle 4"):
        assert secret not in logged


def test_delete_removes_all_session_data(client, uploaded):
    cid = uploaded["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")
    assert client.delete(f"/api/catalogue/{cid}").status_code == 204
    assert len(store) == 0
    for path in ("", "/issues", "/export", "/report", "/comparison", "/summary"):
        assert client.get(f"/api/catalogue/{cid}{path}").status_code == 404


def test_session_cap_evicts_least_recently_used():
    s = CatalogueStore(ttl_seconds=3600, max_sessions=2)
    df = pd.DataFrame({"a": ["1"]})
    a, b = s.create("a.csv", df, {}), s.create("b.csv", df, {})
    s.get(a.catalogue_id)  # a is now more recently used than b
    c = s.create("c.csv", df, {})
    assert len(s) == 2
    assert s.get(b.catalogue_id) is None
    assert s.get(a.catalogue_id) and s.get(c.catalogue_id)


def test_unexpected_input_gives_clean_errors(client, uploaded):
    cid = uploaded["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")
    assert client.get(f"/api/catalogue/{cid}", params={"limit": 100000}).status_code == 422
    assert client.get(f"/api/catalogue/{cid}", params={"offset": -1}).status_code == 422
    assert client.get(f"/api/catalogue/{cid}/issues", params={"severity": "bogus"}).status_code == 422
    assert client.post("/api/issues/xyz/review", json={"action": "accept"}).status_code == 404
    assert client.post("/api/issues/xyz/review", json={}).status_code == 422
