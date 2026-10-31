"""The full product workflow through the HTTP API, ending in downloadable files."""
import csv
import io

from app.deps import get_embedder, store
from app.intelligence.embedding_service import EmbeddingService
from app.main import app
from app.tests.fakes import bow_encoder


def rows_of(resp):
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


def test_upload_to_export_workflow(client, sample_bytes):
    app.dependency_overrides[get_embedder] = lambda: EmbeddingService("fake", encoder=bow_encoder)
    try:
        # 1-3. upload, preview, mapping
        up = client.post("/api/upload", files={"file": ("my catalogue.csv", sample_bytes, "text/csv")}).json()
        cid = up["catalogue_id"]
        assert up["row_count"] == 10 and up["suggested_mapping"]["price"] == "price"

        # 4-5. checks and dashboard numbers
        summary = client.post(f"/api/catalogue/{cid}/analyze", json={"mapping": up["suggested_mapping"]}).json()
        assert summary["errors"] > 0 and summary["potential_duplicates"] is None

        # 6-8. table with flagged cells, then select an issue
        page = client.get(f"/api/catalogue/{cid}", params={"flagged_only": True, "limit": 100}).json()
        assert page["cells"]["3"]["price"]["severity"] == "error"
        issues = {(i["row_id"], i["issue_type"]): i for i in
                  client.get(f"/api/catalogue/{cid}/issues").json()["issues"]}

        # 9-11. accept / edit / reject / ignore, with revalidation and undo
        def act(key, action, value=None):
            return client.post(f"/api/issues/{issues[key]['issue_id']}/review",
                               json={"action": action, "value": value}).json()

        assert act((5, "whitespace"), "accept")["issue"]["status"] == "resolved"
        assert act((3, "negative_price"), "edit", "-1")["issue"]["revalidation_passed"] is False
        act((2, "category_mapping"), "reject")
        act((6, "non_integer_stock"), "ignore")
        client.post(f"/api/issues/{issues[(6, 'non_integer_stock')]['issue_id']}/undo")
        assert act((6, "non_integer_stock"), "accept")["issue"]["status"] == "resolved"

        # similar products (Week 3) never changes data
        sim = client.get(f"/api/catalogue/{cid}/similar-products", params={"semantic_threshold": 0.7}).json()
        assert sim["candidates"]

        # 12. comparison
        comp = client.get(f"/api/catalogue/{cid}/comparison").json()
        changed = {(c["row_id"], c["column"]) for c in comp["changed_cells"]}
        assert changed == {(5, "product_name"), (3, "price"), (6, "stock_quantity")}
        assert len(comp["dismissed_issues"]) == 1 and comp["unresolved_issues"]

        # 13-14. exports
        cleaned = client.get(f"/api/catalogue/{cid}/export")
        report = client.get(f"/api/catalogue/{cid}/report")
        assert cleaned.headers["content-disposition"] == 'attachment; filename="my_catalogue_cleaned.csv"'
        data = rows_of(cleaned)
        assert data[0] == up["columns"] and len(data) == 11
        assert data[6][1] == "Stainless Water Bottle" and data[4][5] == "-1" and data[7][10] == "10"
        assert data[3][3] == "tshirts"  # rejected

        rep = rows_of(report)[1:]
        assert {r[9] for r in rep} >= {"resolved", "applied_but_still_failing", "unresolved"}

        # 15. the original upload was never touched
        assert store.get(cid).original.iat[5, 1] == "  Stainless Water Bottle "
        assert store.get(cid).original.iat[3, 5] == "-500"
    finally:
        app.dependency_overrides.pop(get_embedder, None)
