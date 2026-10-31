import pytest

from app.config import Settings
from app.services import csv_loader as loader

S = Settings(max_upload_bytes=1000, max_rows=3, max_columns=5, session_ttl_seconds=60,
             preview_rows=2, cors_origins=())


def test_preserves_columns_order_and_values(sample_bytes):
    big = Settings(10**7, 1000, 100, 60, 20, ())
    df = loader.load_csv(sample_bytes, big)
    assert list(df.columns)[:3] == ["sku", "product_name", "description"]
    assert list(df.columns)[-1] == "warehouse_note"
    assert df.iloc[5]["product_name"] == "  Stainless Water Bottle "  # untrimmed
    assert df.iloc[3]["price"] == "-500"
    assert df.iloc[8]["sku"] == ""  # empty stays an empty string, not NaN


def test_rejects_non_csv_name():
    with pytest.raises(loader.CsvLoadError):
        loader.validate_filename("data.xlsx")


@pytest.mark.parametrize("data,msg", [
    (b"", "empty"),
    (b"a,b\n", "no data rows"),
    (b"a,a\n1,2\n", "Duplicate"),
    (b"a,,c\n1,2,3\n", "empty column name"),
    (b"a,b\n1,2\x00\n", "binary"),
    (b"a,b\n1,2,3\n", "Malformed"),
])
def test_malformed_files(data, msg):
    with pytest.raises(loader.CsvLoadError, match=msg):
        loader.load_csv(data, S)


def test_limits():
    with pytest.raises(loader.CsvLoadError, match="rows"):
        loader.load_csv(b"a\n1\n2\n3\n4\n", S)
    with pytest.raises(loader.CsvLoadError, match="columns"):
        loader.load_csv(b"a,b,c,d,e,f\n1,2,3,4,5,6\n", S)
    with pytest.raises(loader.CsvLoadError, match="size"):
        loader.load_csv(b"a\n" + b"x" * 2000, S)


def test_suggest_and_validate_mapping():
    cols = ["Item Code", "Title", "Unit Price", "Colour", "extra"]
    m = loader.suggest_mapping(cols)
    assert m == {"sku": "Item Code", "product_name": "Title", "price": "Unit Price", "color": "Colour"}
    assert loader.validate_mapping(m, cols) == m
    with pytest.raises(loader.CsvLoadError):
        loader.validate_mapping({"sku": "nope"}, cols)
    with pytest.raises(loader.CsvLoadError):
        loader.validate_mapping({"sku": "extra", "price": "extra"}, cols)
    with pytest.raises(loader.CsvLoadError):
        loader.validate_mapping({"bogus": "extra"}, cols)


def test_latin1_fallback():
    df = loader.load_csv("a\ncafé\n".encode("cp1252"), S)
    assert df.iloc[0]["a"] == "café"
