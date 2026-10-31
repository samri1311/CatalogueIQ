import csv
import io

import pytest

from app.deps import store
from app.services.export_service import guard_cell, safe_filename


def parse(resp):
    assert resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


def issue(client, cid, row, itype, column=None):
    body = client.get(f"/api/catalogue/{cid}/issues", params={"row_id": row, "issue_type": itype}).json()
    (i,) = [x for x in body["issues"] if column is None or x["column"] == column]
    return i


def review(client, i, action, value=None):
    r = client.post(f"/api/issues/{i['issue_id']}/review", json={"action": action, "value": value})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def cid(client, uploaded):
    c = uploaded["catalogue_id"]
    client.post(f"/api/catalogue/{c}/analyze")
    return c


# --- formula guard -----------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("=1+1", "'=1+1"),
    ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
    ("@SUM(A1)", "'@SUM(A1)"),
    ("-2+3", "'-2+3"),
    ("\t=1", "'\t=1"),
    ("  =HYPERLINK(\"http://x\")", "'  =HYPERLINK(\"http://x\")"),
    ("-500", "-500"),  # a plain negative number is not a formula
    ("+3.5", "+3.5"),
    ("19.99", "19.99"),
    ("Normal text", "Normal text"),
    ("a=b", "a=b"),
    ("", ""),
])
def test_guard_cell(value, expected):
    assert guard_cell(value) == expected


def test_safe_filename():
    assert safe_filename("../../etc/pass wd?.CSV", "cleaned") == "pass_wd_cleaned.csv"
    assert safe_filename("", "report") == "catalogue_report.csv"
    assert safe_filename('a"b\r\n.csv', "x") == "a_b_x.csv"


# --- cleaned export ------------------------------------------------------------------

def test_export_without_changes_equals_upload(client, cid, sample_bytes):
    rows = parse(client.get(f"/api/catalogue/{cid}/export"))
    original = list(csv.reader(io.StringIO(sample_bytes.decode("utf-8"))))
    assert rows[0] == original[0]  # column names and order
    assert len(rows) == len(original)  # row count and order
    assert [r[0] for r in rows] == [r[0] for r in original]
    assert rows[1:] == original[1:]  # every original value, incl. unknown column
    assert rows[0][-1] == "warehouse_note"
    assert rows[6][5] == "$1,299.00"  # a value we would flag is still exported as uploaded


def test_only_approved_changes_are_applied(client, cid, sample_bytes):
    original = list(csv.reader(io.StringIO(sample_bytes.decode("utf-8"))))
    col = original[0].index

    accept = issue(client, cid, 5, "whitespace", "product_name")
    edit = issue(client, cid, 3, "negative_price")
    reject = issue(client, cid, 2, "category_mapping")
    ignore = issue(client, cid, 6, "non_integer_stock")
    review(client, accept, "accept")
    review(client, edit, "edit", "59.90")
    review(client, reject, "reject")
    review(client, ignore, "ignore")

    rows = parse(client.get(f"/api/catalogue/{cid}/export"))
    assert rows[6][col("product_name")] == "Stainless Water Bottle"  # accepted
    assert rows[4][col("price")] == "59.90"  # user-entered
    assert rows[3][col("category")] == original[3][col("category")] == "tshirts"  # rejected: untouched
    assert rows[7][col("stock_quantity")] == "10.0"  # ignored: untouched

    changed = [(r, c) for r in range(1, len(rows)) for c in range(len(rows[0]))
               if rows[r][c] != original[r][c]]
    assert sorted(changed) == [(4, col("price")), (6, col("product_name"))]  # nothing else moved


def test_undo_removes_change_from_export(client, cid, sample_bytes):
    i = issue(client, cid, 5, "whitespace", "product_name")
    review(client, i, "accept")
    client.post(f"/api/issues/{i['issue_id']}/undo")
    assert parse(client.get(f"/api/catalogue/{cid}/export"))[6][1] == "  Stainless Water Bottle "


def test_export_never_modifies_stored_data(client, cid):
    before = store.get(cid).working.copy(deep=True)
    client.get(f"/api/catalogue/{cid}/export")
    client.get(f"/api/catalogue/{cid}/report")
    assert store.get(cid).working.equals(before) and store.get(cid).original.equals(before)


def test_empty_cells_are_empty_strings_not_nan(client, cid):
    text = client.get(f"/api/catalogue/{cid}/export").content.decode("utf-8-sig")
    assert "nan" not in text.lower().replace("nancy", "") and "None" not in text
    assert ",," in text


def test_formula_injection_is_neutralised_in_export_and_report(client):
    malicious = (
        "sku,product_name,category,price,note\n"
        "A1,=HYPERLINK(\"http://evil\"),Tools,10,@cmd\n"
        "A2,Widget,Tools,-500,+1 555 0100\n"
        "A3,Gadget,Tools,=1+1,x\n"
    ).encode()
    cid = client.post("/api/upload", files={"file": ("m.csv", malicious, "text/csv")}).json()["catalogue_id"]
    client.post(f"/api/catalogue/{cid}/analyze")

    rows = parse(client.get(f"/api/catalogue/{cid}/export"))
    assert rows[1][1].startswith("'=") and rows[1][4] == "'@cmd"
    assert rows[2][3] == "-500"  # real number left alone
    assert rows[2][4] == "'+1 555 0100"

    report = parse(client.get(f"/api/catalogue/{cid}/report"))
    values = [c for row in report[1:] for c in row]
    assert not any(c.startswith(("=", "@")) for c in values)
    assert "'=1+1" in values  # the flagged original value, escaped


def test_download_headers_and_404(client, cid):
    r = client.get(f"/api/catalogue/{cid}/export")
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="cat_cleaned.csv"'
    assert client.get(f"/api/catalogue/{cid}/report").headers["content-disposition"].endswith('cat_quality_report.csv"')
    assert client.get("/api/catalogue/nope/export").status_code == 404
    assert client.get("/api/catalogue/nope/report").status_code == 404


# --- quality report ------------------------------------------------------------------

def test_report_columns_and_decisions_and_no_false_claim_of_resolution(client, cid):
    accept = issue(client, cid, 5, "whitespace", "product_name")
    ignore = issue(client, cid, 3, "negative_price")
    review(client, accept, "accept")
    review(client, ignore, "ignore")

    rows = parse(client.get(f"/api/catalogue/{cid}/report"))
    header = rows[0]
    assert header == ["issue_id", "file_line", "sku", "column", "issue_type", "severity",
                      "original_value", "final_value", "review_decision", "resolution_status"]
    by_id = {r[0]: dict(zip(header, r)) for r in rows[1:]}

    a = by_id[accept["issue_id"]]
    assert (a["review_decision"], a["resolution_status"]) == ("accept", "resolved")
    assert a["original_value"] == "  Stainless Water Bottle " and a["final_value"] == "Stainless Water Bottle"
    assert a["file_line"] == "7" and a["sku"] == "SKU-006"

    g = by_id[ignore["issue_id"]]
    assert (g["review_decision"], g["resolution_status"]) == ("ignore", "ignored_left_as_is")
    assert g["original_value"] == g["final_value"] == "-500"

    statuses = {r["resolution_status"] for r in by_id.values()}
    assert "unresolved" in statuses  # untouched issues are reported as unresolved
    assert statuses != {"resolved"}
    assert len(by_id) == len(rows) - 1 == len(store.get(cid).issues)


def test_applied_but_still_failing_is_reported_honestly(client, cid):
    i = issue(client, cid, 3, "negative_price")
    review(client, i, "edit", "-3")  # still negative
    row = next(r for r in parse(client.get(f"/api/catalogue/{cid}/report"))[1:] if r[0] == i["issue_id"])
    assert row[8] == "edit" and row[9] == "applied_but_still_failing" and row[7] == "-3"
