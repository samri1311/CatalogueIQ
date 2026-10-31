import io

import pandas as pd
import pytest

from app.config import Settings
from app.models.issue import IssueType as T
from app.models.issue import Severity
from app.services import csv_loader as loader
from app.services import quality_engine

BIG = Settings(10**7, 1000, 100, 60, 20, ())


@pytest.fixture
def sample(sample_bytes):
    df = loader.load_csv(sample_bytes, BIG)
    return df, loader.suggest_mapping(list(df.columns))


def find(issues, row, itype, column=None):
    return [i for i in issues if i.row_id == row and i.issue_type == itype
            and (column is None or i.column == column)]


def test_analysis_does_not_modify_data(sample):
    df, mapping = sample
    before = df.copy(deep=True)
    quality_engine.analyze(df, mapping)
    pd.testing.assert_frame_equal(df, before)


def test_negative_price_flagged_without_guessing(sample):
    df, m = sample
    (i,) = find(quality_engine.analyze(df, m), 3, T.negative_price)
    assert i.severity == Severity.error
    assert i.proposed_value is None
    assert i.original_value == "-500"


def test_duplicate_skus_flag_every_row(sample):
    issues = quality_engine.analyze(*sample)
    assert find(issues, 3, T.duplicate_sku) and find(issues, 4, T.duplicate_sku)
    assert not find(issues, 0, T.duplicate_sku)


def test_whitespace_has_trimmed_proposal(sample):
    (i,) = find(quality_engine.analyze(*sample), 5, T.whitespace, "product_name")
    assert i.proposed_value == "Stainless Water Bottle"
    assert i.status.value == "ready_for_review"


def test_price_formats(sample):
    issues = quality_engine.analyze(*sample)
    (fmt,) = find(issues, 5, T.inconsistent_format, "price")
    assert fmt.proposed_value == "1299.00"
    assert find(issues, 7, T.invalid_number, "price")  # "abc"
    assert find(issues, 9, T.invalid_number, "price")  # "abc 12"


def test_stock_rules(sample):
    issues = quality_engine.analyze(*sample)
    assert find(issues, 4, T.negative_stock)
    (dec,) = find(issues, 6, T.non_integer_stock)
    assert dec.proposed_value == "10"


def test_urls(sample):
    issues = quality_engine.analyze(*sample)
    assert find(issues, 5, T.malformed_url, "product_url")
    assert find(issues, 8, T.malformed_url, "product_url")  # ftp://
    assert not find(issues, 0, T.malformed_url)


def test_missing_required_and_optional(sample):
    issues = quality_engine.analyze(*sample)
    (m,) = find(issues, 8, T.missing_required, "sku")
    assert m.severity == Severity.error
    opt = find(issues, 7, T.missing_optional, "description")
    assert opt and opt[0].severity == Severity.info


def test_currency(sample):
    issues = quality_engine.analyze(*sample)
    assert find(issues, 8, T.invalid_currency)
    assert find(issues, 6, T.missing_currency)
    (lower,) = find(issues, 5, T.inconsistent_format, "currency")
    assert lower.proposed_value == "USD"


def test_category_mapping_and_variants(sample):
    issues = quality_engine.analyze(*sample)
    (cm,) = find(issues, 2, T.category_mapping)
    assert cm.proposed_value == "T-Shirts"
    (v,) = find(issues, 6, T.inconsistent_format, "category")
    assert v.proposed_value == "Kitchen" or v.proposed_value == "kitchen"


def test_unknown_column_untouched_and_unmapped_ok():
    df = pd.read_csv(io.StringIO("sku,price,extra\nA,1,  x\n"), dtype=str, keep_default_na=False)
    issues = quality_engine.analyze(df, {"sku": "sku", "price": "price"})
    # 'extra' is not mapped but still checked for whitespace
    assert [i.issue_type for i in issues] == [T.whitespace]
    assert issues[0].column == "extra"


def test_clean_data_has_no_issues():
    df = pd.DataFrame({"sku": ["A", "B"], "name": ["x", "y"], "cat": ["c", "c"], "p": ["1.5", "2"]})
    m = {"sku": "sku", "product_name": "name", "category": "cat", "price": "p"}
    assert quality_engine.analyze(df, m) == []
