"""Cleaned-catalogue and quality-report CSV export.

The cleaned CSV is the working copy, which only ever differs from the upload
where the user accepted a proposal or typed an edit, so rejected or ignored
suggestions can never appear in it. Column names/order, row order and unknown
columns are preserved exactly.

Every cell is passed through a formula-injection guard, because catalogue text
can end up opened in Excel or Sheets.
"""
from __future__ import annotations

import csv
import io
import re

from app.models.issue import IssueStatus
from app.services.catalogue_store import Catalogue

# Characters that make a spreadsheet treat a cell as a formula.
_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
# Plain numbers such as -500 or +3.5 are harmless and must stay numeric.
_PLAIN_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")

REPORT_COLUMNS = [
    "issue_id", "file_line", "sku", "column", "issue_type", "severity",
    "original_value", "final_value", "review_decision", "resolution_status",
]

_RESOLUTION = {
    IssueStatus.resolved: "resolved",
    IssueStatus.accepted: "applied_but_still_failing",
    IssueStatus.edited: "applied_but_still_failing",
    IssueStatus.rejected: "rejected_left_as_is",
    IssueStatus.ignored: "ignored_left_as_is",
    IssueStatus.open: "unresolved",
    IssueStatus.ready_for_review: "unresolved",
    IssueStatus.needs_investigation: "unresolved",
}


def guard_cell(value: str) -> str:
    """Prefix risky values with an apostrophe so spreadsheets show them as text."""
    if not value:
        return ""
    probe = value.lstrip(" ")
    if probe and probe[0] in _TRIGGERS and not _PLAIN_NUMBER.match(value.strip()):
        return "'" + value
    return value


def _to_bytes(header: list[str], rows) -> tuple[bytes, int]:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    escaped = 0
    writer.writerow([guard_cell(h) for h in header])
    for row in rows:
        out = []
        for v in row:
            v = "" if v is None else str(v)  # empty cells are always written as ""
            g = guard_cell(v)
            escaped += g != v
            out.append(g)
        writer.writerow(out)
    # utf-8 with BOM so Excel reads accented characters correctly.
    return buf.getvalue().encode("utf-8-sig"), escaped


def cleaned_csv(cat: Catalogue) -> tuple[bytes, int]:
    """Return (csv bytes, number of cells escaped by the formula guard)."""
    return _to_bytes(list(cat.working.columns), cat.working.to_numpy().tolist())


def report_csv(cat: Catalogue) -> tuple[bytes, int]:
    rows = []
    for i in cat.issues:
        rows.append([
            i.issue_id, i.row_id + 2,  # +2: 1-based and the header is line 1
            i.sku or "", i.column, i.issue_type.value, i.severity.value,
            i.original_value, i.current_value,
            i.review_action.value if i.review_action else "none",
            _RESOLUTION[i.status],
        ])
    return _to_bytes(REPORT_COLUMNS, rows)


def safe_filename(upload_name: str, suffix: str) -> str:
    stem = re.sub(r"\.csv$", "", upload_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "catalogue"
    return f"{stem[:80]}_{suffix}.csv"
