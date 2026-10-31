import pandas as pd
import pytest

from app.deps import store
from app.services import quality_engine


@pytest.fixture
def cid(client, uploaded):
    c = uploaded["catalogue_id"]
    assert client.post(f"/api/catalogue/{c}/analyze").status_code == 200
    return c


def get_issue(client, cid, row, itype, column=None):
    body = client.get(f"/api/catalogue/{cid}/issues", params={"row_id": row, "issue_type": itype}).json()
    found = [i for i in body["issues"] if column is None or i["column"] == column]
    assert len(found) == 1, (row, itype, found)
    return found[0]


def review(client, issue_id, action, value=None):
    return client.post(f"/api/issues/{issue_id}/review", json={"action": action, "value": value})


def undo(client, issue_id):
    return client.post(f"/api/issues/{issue_id}/undo")


def working(cid, row, col):
    return store.get(cid).working.at[row, col]


def original(cid, row, col):
    return store.get(cid).original.at[row, col]


def test_accept_applies_to_working_copy_only_and_resolves(client, cid):
    i = get_issue(client, cid, 5, "whitespace", "product_name")
    r = review(client, i["issue_id"], "accept")
    assert r.status_code == 200
    body = r.json()
    assert body["issue"]["status"] == "resolved"  # revalidation passed
    assert body["issue"]["review_action"] == "accept"
    assert body["issue"]["revalidation_passed"] is True
    assert working(cid, 5, "product_name") == "Stainless Water Bottle"
    assert original(cid, 5, "product_name") == "  Stainless Water Bottle "
    assert body["original_value"] == "  Stainless Water Bottle "
    assert body["current_value"] == "Stainless Water Bottle"


def test_accept_without_proposal_is_rejected(client, cid):
    i = get_issue(client, cid, 3, "negative_price")
    assert i["proposed_value"] is None
    assert review(client, i["issue_id"], "accept").status_code == 400
    assert working(cid, 3, "price") == "-500"


def test_edit_still_invalid_is_not_marked_resolved(client, cid):
    i = get_issue(client, cid, 3, "negative_price")
    r = review(client, i["issue_id"], "edit", "-3")
    body = r.json()
    assert body["issue"]["status"] == "edited"
    assert body["issue"]["revalidation_passed"] is False
    assert working(cid, 3, "price") == "-3"


def test_edit_valid_resolves_and_undo_restores(client, cid):
    i = get_issue(client, cid, 3, "negative_price")
    r = review(client, i["issue_id"], "edit", "59.90")
    assert r.json()["issue"]["status"] == "resolved"
    assert working(cid, 3, "price") == "59.90"

    u = undo(client, i["issue_id"])
    assert u.status_code == 200
    assert u.json()["issue"]["status"] == "needs_investigation"
    assert u.json()["issue"]["review_action"] is None
    assert working(cid, 3, "price") == "-500"
    assert original(cid, 3, "price") == "-500"


def test_edit_introducing_new_problem_creates_new_issue(client, cid):
    i = get_issue(client, cid, 3, "negative_price")
    body = review(client, i["issue_id"], "edit", "abc").json()
    types = {c["issue_type"] for c in body["changed_issues"]}
    assert "invalid_number" in types
    assert body["issue"]["status"] == "resolved"  # negative price itself is gone
    new = get_issue(client, cid, 3, "invalid_number")
    assert new["original_value"] == "-500" and new["current_value"] == "abc"


def test_edit_validation_errors(client, cid):
    i = get_issue(client, cid, 3, "negative_price")
    assert review(client, i["issue_id"], "edit").status_code == 400
    assert review(client, i["issue_id"], "edit", "-500").status_code == 400
    assert review(client, i["issue_id"], "edit", "x" * 10_001).status_code == 400
    assert review(client, i["issue_id"], "undo").status_code == 400
    assert review(client, "nope", "ignore").status_code == 404


@pytest.mark.parametrize("action,status", [("reject", "rejected"), ("ignore", "ignored")])
def test_reject_and_ignore_keep_value_and_can_be_undone(client, cid, action, status):
    i = get_issue(client, cid, 5, "whitespace", "product_name")
    body = review(client, i["issue_id"], action).json()
    assert body["issue"]["status"] == status
    assert working(cid, 5, "product_name") == "  Stainless Water Bottle "

    page = client.get(f"/api/catalogue/{cid}", params={"flagged_only": True}).json()
    cell = page["cells"]["5"]["product_name"]
    assert cell["state"] == "dismissed" and cell["severity"] is None

    assert review(client, i["issue_id"], "accept").status_code == 409  # must undo first
    assert undo(client, i["issue_id"]).json()["issue"]["status"] == "ready_for_review"
    assert undo(client, i["issue_id"]).status_code == 409  # nothing left to undo


def test_duplicate_sku_revalidates_other_rows_and_undo_reopens(client, cid):
    a = get_issue(client, cid, 3, "duplicate_sku")
    b = get_issue(client, cid, 4, "duplicate_sku")
    body = review(client, b["issue_id"], "edit", "SKU-005").json()
    assert body["issue"]["status"] == "resolved"
    after_a = get_issue(client, cid, 3, "duplicate_sku")
    assert after_a["status"] == "resolved"  # other row's duplicate also cleared
    assert a["issue_id"] == after_a["issue_id"]

    undo(client, b["issue_id"])
    assert get_issue(client, cid, 3, "duplicate_sku")["status"] == "needs_investigation"
    assert get_issue(client, cid, 4, "duplicate_sku")["status"] == "needs_investigation"


def test_changes_to_one_cell_are_undone_newest_first():
    df = pd.DataFrame({"sku": ["A"], "name": ["x"], "cat": ["c"], "price": [" $5 "]})
    m = {"sku": "sku", "product_name": "name", "category": "cat", "price": "price"}
    cat = store.create("t.csv", df, m)
    cat.issues = quality_engine.analyze(cat.original, m)
    cat.analyzed = True
    from app.services import issue_manager as im
    ws = next(i for i in cat.issues if i.issue_type.value == "whitespace")
    im.review_issue(cat, ws.issue_id, im.ReviewAction.accept)
    fmt = next(i for i in cat.issues if i.issue_type.value == "inconsistent_format")
    im.review_issue(cat, fmt.issue_id, im.ReviewAction.accept)
    assert cat.working.at[0, "price"] == "5"

    with pytest.raises(im.ReviewError) as e:
        im.undo_issue(cat, ws.issue_id)
    assert e.value.status_code == 409
    im.undo_issue(cat, fmt.issue_id)
    assert cat.working.at[0, "price"] == "$5"
    im.undo_issue(cat, ws.issue_id)
    assert cat.working.at[0, "price"] == " $5 "
    assert cat.original.at[0, "price"] == " $5 "
    store.delete(cat.catalogue_id)


def test_whitespace_fix_does_not_hide_other_problem():
    df = pd.DataFrame({"sku": ["A"], "name": ["x"], "cat": ["c"], "price": [" abc "]})
    m = {"sku": "sku", "product_name": "name", "category": "cat", "price": "price"}
    cat = store.create("t.csv", df, m)
    cat.issues = quality_engine.analyze(cat.original, m)
    from app.services import issue_manager as im
    ws = next(i for i in cat.issues if i.issue_type.value == "whitespace")
    im.review_issue(cat, ws.issue_id, im.ReviewAction.accept)
    status = {i.issue_type.value: i.status.value for i in cat.issues}
    assert status == {"whitespace": "resolved", "invalid_number": "needs_investigation"}
    store.delete(cat.catalogue_id)


def test_original_never_changes_through_many_actions(client, uploaded, cid, sample_bytes):
    before = store.get(cid).original.copy(deep=True)
    for itype, row in [("whitespace", 5), ("negative_price", 3), ("non_integer_stock", 6)]:
        i = get_issue(client, cid, row, itype)
        review(client, i["issue_id"], "accept" if i["proposed_value"] else "edit", "7")
        undo(client, i["issue_id"])
    pd.testing.assert_frame_equal(store.get(cid).original, before)
    assert store.get(cid).working.equals(before)  # all undone


def test_summary_reflects_reviews_and_reanalyze_resets(client, cid):
    s0 = client.get(f"/api/catalogue/{cid}/summary").json()
    i = get_issue(client, cid, 5, "whitespace", "product_name")
    review(client, i["issue_id"], "accept")
    s1 = client.get(f"/api/catalogue/{cid}/summary").json()
    assert s1["warnings"] == s0["warnings"] - 1
    assert s1["by_status"]["resolved"] == 1

    ig = get_issue(client, cid, 3, "negative_price")
    review(client, ig["issue_id"], "ignore")
    s2 = client.get(f"/api/catalogue/{cid}/summary").json()
    assert s2["by_status"]["ignored"] == 1
    assert s2["errors"] == s1["errors"] - 1  # ignored issues are not counted as open...
    comp = client.get(f"/api/catalogue/{cid}/comparison").json()
    assert len(comp["dismissed_issues"]) == 1  # ...but are still reported, never hidden

    s3 = client.post(f"/api/catalogue/{cid}/analyze").json()
    assert s3["by_status"].get("resolved") is None and s3["warnings"] == s0["warnings"]
    assert working(cid, 5, "product_name") == "  Stainless Water Bottle "


def test_comparison_lists_changes_and_unresolved(client, cid):
    i = get_issue(client, cid, 2, "category_mapping")
    review(client, i["issue_id"], "accept")
    comp = client.get(f"/api/catalogue/{cid}/comparison").json()
    (ch,) = comp["changed_cells"]
    assert (ch["row_id"], ch["column"], ch["original_value"], ch["current_value"]) == (
        2, "category", "tshirts", "T-Shirts")
    assert ch["sku"] == "SKU-003" and ch["review_actions"] == ["accept"]
    assert comp["resolved_count"] >= 1
    assert all(u["status"] not in ("resolved", "ignored", "rejected") for u in comp["unresolved_issues"])


def test_table_search_filter_and_cells(client, cid):
    p = client.get(f"/api/catalogue/{cid}", params={"q": "wireless mouse"}).json()
    assert p["total_rows"] == 1 and p["rows"][0]["__row_id__"] == "7"
    assert p["cells"]["7"]["price"] == {
        "severity": "error", "state": "open",
        "issue_ids": p["cells"]["7"]["price"]["issue_ids"]}

    errs = client.get(f"/api/catalogue/{cid}", params={"severity": "error", "limit": 100}).json()
    ids = {r["__row_id__"] for r in errs["rows"]}
    assert "3" in ids and "0" not in ids
    assert "warehouse_note" not in errs["checked_columns"]
    assert "price" in errs["checked_columns"]

    p = client.get(f"/api/catalogue/{cid}", params={"flagged_only": True, "limit": 2, "offset": 2}).json()
    assert len(p["rows"]) == 2 and p["total_rows"] > 4


def test_resolved_cell_state_after_fix(client, cid):
    i = get_issue(client, cid, 5, "whitespace", "product_name")
    review(client, i["issue_id"], "accept")
    p = client.get(f"/api/catalogue/{cid}", params={"q": "stainless water bottle"}).json()
    cell = p["cells"]["5"]["product_name"]
    assert cell["state"] == "resolved" and cell["severity"] is None
