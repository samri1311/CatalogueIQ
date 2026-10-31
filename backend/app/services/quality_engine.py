"""Deterministic data-quality checks.

`analyze` is a pure function: it reads the DataFrame and returns a list of
Issue objects. It never modifies the data. A proposed_value is only set when
the intended result is unambiguous (e.g. trimming whitespace); unknown facts
such as a negative price are flagged, never "fixed".
"""
from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd

from app.models.issue import Issue, IssueStatus, IssueType, Severity
from app.services import normalizer as nz
from app.services.csv_loader import REQUIRED_FIELDS

OPTIONAL_INFO_FIELDS = ["description", "brand", "image_url"]
VARIANT_CHECK_FIELDS = ["category", "brand", "color", "material"]
URL_FIELDS = ["product_url", "image_url"]


def _initial_status(severity: Severity, proposed: str | None) -> IssueStatus:
    if proposed is not None:
        return IssueStatus.ready_for_review
    # An error with no justified fix means a fact is unknown and must be looked up.
    return IssueStatus.needs_investigation if severity == Severity.error else IssueStatus.open


class _Collector:
    def __init__(self, df: pd.DataFrame, mapping: dict[str, str]):
        self.df = df
        self.mapping = mapping
        self.issues: list[Issue] = []
        sku_col = mapping.get("sku")
        self.skus = df[sku_col].tolist() if sku_col else [None] * len(df)

    def add(self, row: int, column: str, itype: IssueType, severity: Severity,
            explanation: str, proposed: str | None = None) -> None:
        value = self.df.iat[row, self.df.columns.get_loc(column)]
        sku = self.skus[row]
        self.issues.append(Issue(
            row_id=row,
            sku=sku.strip() if isinstance(sku, str) and sku.strip() else None,
            column=column,
            original_value=value,
            current_value=value,
            issue_type=itype,
            severity=severity,
            explanation=explanation,
            proposed_value=proposed,
            status=_initial_status(severity, proposed),
        ))


def analyze(df: pd.DataFrame, mapping: dict[str, str]) -> list[Issue]:
    c = _Collector(df, mapping)
    _whitespace(c)
    _required_and_optional(c)
    _duplicate_skus(c)
    _price(c)
    _stock(c)
    _urls(c)
    _currency(c)
    _category_mapping(c)
    _variants(c)
    c.issues.sort(key=lambda i: (i.row_id, list(df.columns).index(i.column)))
    return c.issues


def _values(c: _Collector, field: str):
    col = c.mapping.get(field)
    if not col:
        return None, []
    return col, c.df[col].tolist()


def _whitespace(c: _Collector) -> None:
    for col in c.df.columns:
        for row, v in enumerate(c.df[col].tolist()):
            if v != v.strip() and v.strip():
                c.add(row, col, IssueType.whitespace, Severity.warning,
                      "Value has leading or trailing whitespace.", v.strip())


def _required_and_optional(c: _Collector) -> None:
    for field in REQUIRED_FIELDS:
        col, vals = _values(c, field)
        for row, v in enumerate(vals):
            if nz.is_blank(v):
                c.add(row, col, IssueType.missing_required, Severity.error,
                      f"Required field '{field}' is empty.")
    for field in OPTIONAL_INFO_FIELDS:
        col, vals = _values(c, field)
        for row, v in enumerate(vals):
            if nz.is_blank(v):
                c.add(row, col, IssueType.missing_optional, Severity.info,
                      f"Optional field '{field}' is empty.")


def _duplicate_skus(c: _Collector) -> None:
    col, vals = _values(c, "sku")
    groups: dict[str, list[int]] = defaultdict(list)
    for row, v in enumerate(vals):
        if not nz.is_blank(v):
            groups[nz.normalize_key(v)].append(row)
    for rows in groups.values():
        if len(rows) > 1:
            for row in rows:
                others = [str(r + 2) for r in rows if r != row]  # +2: 1-based, after header
                c.add(row, col, IssueType.duplicate_sku, Severity.error,
                      f"SKU is used by {len(rows)} rows (also on file line(s) {', '.join(others)}).")


def _price(c: _Collector) -> None:
    col, vals = _values(c, "price")
    for row, raw in enumerate(vals):
        v = raw.strip()
        if not v:
            continue  # reported as missing_required
        num = nz.parse_decimal_strict(v)
        proposed = None
        if num is None:
            cleaned = nz.clean_price_text(v)
            num = nz.parse_decimal_strict(cleaned) if cleaned else None
            if num is None:
                c.add(row, col, IssueType.invalid_number, Severity.error,
                      f"Price '{v}' is not a valid number.")
                continue
            proposed = cleaned
        if num < 0:
            c.add(row, col, IssueType.negative_price, Severity.error,
                  f"Price {v} is negative. The correct value is unknown, so none is proposed.")
        elif num == 0:
            c.add(row, col, IssueType.zero_price, Severity.warning,
                  "Price is zero; confirm this is intentional.")
        if proposed is not None and num >= 0:
            c.add(row, col, IssueType.inconsistent_format, Severity.warning,
                  "Price contains a currency symbol or thousands separator.", proposed)


def _stock(c: _Collector) -> None:
    col, vals = _values(c, "stock_quantity")
    for row, raw in enumerate(vals):
        v = raw.strip()
        if not v:
            continue
        as_int = nz.parse_int_strict(v)
        if as_int is not None:
            if as_int < 0:
                c.add(row, col, IssueType.negative_stock, Severity.error,
                      f"Stock quantity {v} is negative.")
            continue
        as_float = nz.parse_decimal_strict(v)
        if as_float is None:
            c.add(row, col, IssueType.invalid_number, Severity.error,
                  f"Stock quantity '{v}' is not a valid number.")
        elif as_float < 0:
            c.add(row, col, IssueType.negative_stock, Severity.error,
                  f"Stock quantity {v} is negative.")
        elif as_float == int(as_float):
            c.add(row, col, IssueType.non_integer_stock, Severity.warning,
                  "Stock quantity is written as a decimal.", str(int(as_float)))
        else:
            c.add(row, col, IssueType.non_integer_stock, Severity.warning,
                  f"Stock quantity {v} is not a whole number.")


def _urls(c: _Collector) -> None:
    for field in URL_FIELDS:
        col, vals = _values(c, field)
        for row, raw in enumerate(vals):
            if raw.strip() and not nz.is_valid_url(raw):
                c.add(row, col, IssueType.malformed_url, Severity.error,
                      "Not a valid http(s) URL.")


def _currency(c: _Collector) -> None:
    col, vals = _values(c, "currency")
    if not col:
        return
    price_col, prices = _values(c, "price")
    for row, raw in enumerate(vals):
        v = raw.strip()
        if not v:
            if price_col and not nz.is_blank(prices[row]):
                c.add(row, col, IssueType.missing_currency, Severity.warning,
                      "A price is present but the currency is empty.")
        elif v in nz.ISO_CURRENCIES:
            continue
        elif v.upper() in nz.ISO_CURRENCIES:
            c.add(row, col, IssueType.inconsistent_format, Severity.warning,
                  "Currency code should be upper case.", v.upper())
        else:
            c.add(row, col, IssueType.invalid_currency, Severity.error,
                  f"'{v}' is not a recognised ISO 4217 currency code.")


def _category_mapping(c: _Collector) -> None:
    col, vals = _values(c, "category")
    for row, raw in enumerate(vals):
        v = raw.strip()
        target = nz.CATEGORY_MAP.get(nz.normalize_key(v)) if v else None
        if target and v != target:
            c.add(row, col, IssueType.category_mapping, Severity.warning,
                  f"'{v}' is a known variant of '{target}'.", target)


def _variants(c: _Collector) -> None:
    """Flag values that differ only by case/spacing from the dominant spelling."""
    already = {(i.row_id, i.column) for i in c.issues
               if i.issue_type in (IssueType.category_mapping, IssueType.whitespace)}
    for field in VARIANT_CHECK_FIELDS:
        col, vals = _values(c, field)
        spellings: dict[str, Counter] = defaultdict(Counter)
        for v in vals:
            if not nz.is_blank(v):
                spellings[nz.normalize_key(v)][" ".join(v.split())] += 1
        for row, raw in enumerate(vals):
            if nz.is_blank(raw) or (row, col) in already:
                continue
            counts = spellings[nz.normalize_key(raw)]
            if len(counts) < 2:
                continue
            best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            if " ".join(raw.split()) != best:
                c.add(row, col, IssueType.inconsistent_format, Severity.warning,
                      f"'{raw.strip()}' differs from the more common spelling '{best}'.", best)
