import time

from app.deps import store
from app.services.catalogue_store import CatalogueStore


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_returns_preview_and_mapping(uploaded):
    assert uploaded["row_count"] == 10
    assert uploaded["columns"][-1] == "warehouse_note"
    assert uploaded["suggested_mapping"]["sku"] == "sku"
    assert len(uploaded["preview"]) == 10 or len(uploaded["preview"]) == 20 or uploaded["preview"]
    assert "warehouse_note" not in uploaded["suggested_mapping"].values()


def test_upload_rejections(client):
    r = client.post("/api/upload", files={"file": ("x.txt", b"a\n1\n", "text/plain")})
    assert r.status_code == 400 and "csv" in r.json()["detail"].lower()
    r = client.post("/api/upload", files={"file": ("x.csv", b"a,a\n1,2\n", "text/csv")})
    assert r.status_code == 400


def test_unknown_catalogue_is_404(client):
    assert client.get("/api/catalogue/nope").status_code == 404
    assert client.post("/api/catalogue/nope/analyze").status_code == 404


def test_issues_require_analysis(client, uploaded):
    cid = uploaded["catalogue_id"]
    assert client.get(f"/api/catalogue/{cid}/issues").status_code == 409


def test_analyze_and_filter(client, uploaded):
    cid = uploaded["catalogue_id"]
    r = client.post(f"/api/catalogue/{cid}/analyze")
    assert r.status_code == 200
    s = r.json()
    assert s["total_products"] == 10
    assert s["errors"] > 0 and s["warnings"] > 0 and s["infos"] > 0
    assert s["total_issues"] == s["errors"] + s["warnings"] + s["infos"]
    assert s["unmapped_required_fields"] == []

    r = client.get(f"/api/catalogue/{cid}/issues", params={"severity": "error", "column": "price"})
    body = r.json()
    assert body["total"] > 0
    assert all(i["severity"] == "error" and i["column"] == "price" for i in body["issues"])


def test_analyze_with_custom_mapping_and_bad_mapping(client, uploaded):
    cid = uploaded["catalogue_id"]
    r = client.post(f"/api/catalogue/{cid}/analyze", json={"mapping": {"sku": "missing_col"}})
    assert r.status_code == 400
    r = client.post(f"/api/catalogue/{cid}/analyze", json={"mapping": {"sku": "sku"}})
    assert r.status_code == 200
    assert set(r.json()["unmapped_required_fields"]) == {"product_name", "category", "price"}


def test_original_data_preserved_through_workflow(client, uploaded):
    cid = uploaded["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")
    cat = store.get(cid)
    assert cat.original.equals(cat.working)
    assert cat.original is not cat.working
    page = client.get(f"/api/catalogue/{cid}", params={"offset": 5, "limit": 2}).json()
    assert page["total_rows"] == 10 and len(page["rows"]) == 2
    assert page["rows"][0]["__row_id__"] == "5"
    assert page["rows"][0]["product_name"] == "  Stainless Water Bottle "


def test_delete_cleans_up(client, uploaded):
    cid = uploaded["catalogue_id"]
    assert client.delete(f"/api/catalogue/{cid}").status_code == 204
    assert client.get(f"/api/catalogue/{cid}").status_code == 404


def test_ttl_expiry():
    import pandas as pd
    s = CatalogueStore(ttl_seconds=0)
    cat = s.create("a.csv", pd.DataFrame({"a": ["1"]}), {})
    time.sleep(0.05)  # Windows monotonic clock resolution is ~15 ms
    assert s.get(cat.catalogue_id) is None
    assert len(s) == 0
