"""Issue ledger: review actions, undo, and revalidation of the working copy.

Rules this module enforces:
  * The original DataFrame is never written to; only `working` changes.
  * Accepting or editing a value never marks a cell valid on its own. The
    whole working copy is revalidated and an issue becomes `resolved` only if
    its problem is genuinely gone. Otherwise it stays accepted/edited with
    revalidation_passed=False.
  * Undo restores the previous cell value, but only if no later change was
    made to the same cell (changes to a cell are undone newest-first).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import numpy as np

from app.models.issue import Issue, IssueStatus, ReviewAction, Severity
from app.services import quality_engine
from app.services.catalogue_store import Catalogue, Snapshot

# Waiting for a decision.
PENDING = {IssueStatus.open, IssueStatus.ready_for_review, IssueStatus.needs_investigation}
# Problem still present in the working copy (pending, or applied but revalidation failed).
OPEN = PENDING | {IssueStatus.accepted, IssueStatus.edited}
DISMISSED = {IssueStatus.rejected, IssueStatus.ignored}
MAX_EDIT_LENGTH = 10_000

_SEVERITY_RANK = {Severity.error: 3, Severity.warning: 2, Severity.info: 1}


class ReviewError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _cell(cat: Catalogue, row: int, col: str) -> str:
    return cat.working.at[row, col]


def _fingerprint(i: Issue) -> tuple:
    return (i.status, i.review_action, i.current_value, i.revalidation_passed, i.proposed_value)


def _touch(i: Issue) -> None:
    i.version += 1
    i.updated_at = datetime.now(timezone.utc)


def find_issue(cat: Catalogue, issue_id: str) -> Issue:
    for i in cat.issues:
        if i.issue_id == issue_id:
            return i
    raise ReviewError(404, "Issue not found.")


def reconcile(cat: Catalogue) -> list[Issue]:
    """Revalidate the working copy and bring the ledger in line with it.

    Returns issues that changed or were newly created.
    """
    fresh = {(i.row_id, i.column, i.issue_type): i
             for i in quality_engine.analyze(cat.working, cat.mapping)}
    changed: list[Issue] = []
    seen = set()

    for issue in cat.issues:
        before = _fingerprint(issue)
        key = (issue.row_id, issue.column, issue.issue_type)
        seen.add(key)
        present = fresh.get(key)
        issue.current_value = _cell(cat, issue.row_id, issue.column)

        if issue.status in PENDING and present is None:
            issue.status = IssueStatus.resolved
        elif issue.status in (IssueStatus.accepted, IssueStatus.edited):
            if present is None:
                issue.status, issue.revalidation_passed = IssueStatus.resolved, True
            else:
                issue.revalidation_passed = False
        elif issue.status == IssueStatus.resolved and present is not None:
            # The problem came back (e.g. after an undo or a later edit).
            issue.status = present.status
            issue.proposed_value = present.proposed_value
            issue.review_action = None
            issue.revalidation_passed = None

        if _fingerprint(issue) != before:
            _touch(issue)
            changed.append(issue)

    added = False
    for key, f in fresh.items():
        if key in seen:
            continue
        new = f.model_copy(update={
            "original_value": cat.original.at[f.row_id, f.column],
            "current_value": _cell(cat, f.row_id, f.column),
        })
        cat.issues.append(new)
        changed.append(new)
        added = True

    if added:
        order = {c: n for n, c in enumerate(cat.working.columns)}
        cat.issues.sort(key=lambda i: (i.row_id, order[i.column]))
    return changed


def review_issue(cat: Catalogue, issue_id: str, action: ReviewAction,
                 value: str | None = None) -> tuple[Issue, list[Issue]]:
    issue = find_issue(cat, issue_id)
    if action == ReviewAction.undo:
        raise ReviewError(400, "Use the undo endpoint to undo.")
    if issue.status not in PENDING:
        raise ReviewError(409, f"Issue is already '{issue.status.value}'. Undo it before reviewing again.")

    key = (issue.row_id, issue.column)
    current = _cell(cat, *key)
    new_value: str | None = None
    if action == ReviewAction.accept:
        if issue.proposed_value is None:
            raise ReviewError(400, "This issue has no proposed value to accept. Edit it instead.")
        new_value = issue.proposed_value
    elif action == ReviewAction.edit:
        if value is None:
            raise ReviewError(400, "A replacement value is required for edit.")
        if len(value) > MAX_EDIT_LENGTH:
            raise ReviewError(400, f"Value is longer than {MAX_EDIT_LENGTH} characters.")
        if value == current:
            raise ReviewError(400, "The new value is the same as the current value.")
        new_value = value

    snap = Snapshot(issue.status, issue.review_action, issue.revalidation_passed,
                    current, changed_value=new_value is not None)
    cat.history.setdefault(issue_id, []).append(snap)

    if new_value is not None:
        cat.working.at[issue.row_id, issue.column] = new_value
        cat.cell_stack.setdefault(key, []).append(issue_id)

    issue.review_action = action
    issue.status = {
        ReviewAction.accept: IssueStatus.accepted,
        ReviewAction.edit: IssueStatus.edited,
        ReviewAction.reject: IssueStatus.rejected,
        ReviewAction.ignore: IssueStatus.ignored,
    }[action]
    _touch(issue)

    changed = reconcile(cat)
    if issue not in changed:
        changed.insert(0, issue)
    return issue, changed


def undo_issue(cat: Catalogue, issue_id: str) -> tuple[Issue, list[Issue]]:
    issue = find_issue(cat, issue_id)
    stack = cat.history.get(issue_id)
    if not stack:
        raise ReviewError(409, "Nothing to undo for this issue.")
    snap = stack[-1]
    key = (issue.row_id, issue.column)

    if snap.changed_value:
        cells = cat.cell_stack.get(key, [])
        if not cells or cells[-1] != issue_id:
            raise ReviewError(409, "A later change was made to this cell. Undo that change first.")
        cells.pop()
        cat.working.at[issue.row_id, issue.column] = snap.prev_value

    stack.pop()
    issue.status = snap.status
    issue.review_action = snap.review_action
    issue.revalidation_passed = snap.revalidation_passed
    _touch(issue)

    changed = reconcile(cat)
    if issue not in changed:
        changed.insert(0, issue)
    return issue, changed


def summarize(cat: Catalogue) -> dict:
    open_issues = [i for i in cat.issues if i.status in OPEN]
    sev = Counter(i.severity for i in open_issues)
    return {
        "catalogue_id": cat.catalogue_id,
        "total_products": len(cat.original),
        "total_issues": len(cat.issues),
        "errors": sev[Severity.error],
        "warnings": sev[Severity.warning],
        "infos": sev[Severity.info],
        "flagged_cells": len({(i.row_id, i.column) for i in open_issues}),
        "flagged_rows": len({i.row_id for i in open_issues}),
        "by_type": dict(Counter(i.issue_type.value for i in open_issues)),
        "by_status": dict(Counter(i.status.value for i in cat.issues)),
        "potential_duplicates": cat.potential_duplicates,
        "unmapped_required_fields": [
            f for f in quality_engine.REQUIRED_FIELDS if f not in cat.mapping
        ],
    }


def cell_states(cat: Catalogue, row_ids: list[int]) -> dict[str, dict[str, dict]]:
    """Per-cell issue summary for the given rows, keyed row_id -> column."""
    wanted = set(row_ids)
    out: dict[str, dict[str, dict]] = {}
    for i in cat.issues:
        if i.row_id not in wanted:
            continue
        cell = out.setdefault(str(i.row_id), {}).setdefault(
            i.column, {"severity": None, "state": "resolved", "issue_ids": []})
        cell["issue_ids"].append(i.issue_id)
        if i.status in OPEN:
            cell["state"] = "open"
            if cell["severity"] is None or _SEVERITY_RANK[i.severity] > _SEVERITY_RANK[Severity(cell["severity"])]:
                cell["severity"] = i.severity.value
        elif i.status in DISMISSED and cell["state"] != "open":
            cell["state"] = "dismissed"
    return out


def rows_with_open_issues(cat: Catalogue, severity: Severity | None) -> set[int]:
    return {i.row_id for i in cat.issues
            if i.status in OPEN and (severity is None or i.severity == severity)}


def comparison(cat: Catalogue) -> dict:
    orig, work = cat.original.to_numpy(), cat.working.to_numpy()
    cols = list(cat.original.columns)
    sku_col = cat.mapping.get("sku")
    by_cell: dict[tuple[int, str], list[Issue]] = {}
    for i in cat.issues:
        by_cell.setdefault((i.row_id, i.column), []).append(i)

    changes = []
    for r, c in np.argwhere(orig != work):
        row, col = int(r), cols[int(c)]
        related = [i for i in by_cell.get((row, col), [])
                   if i.review_action in (ReviewAction.accept, ReviewAction.edit)]
        sku = cat.original.at[row, sku_col] if sku_col else None
        changes.append({
            "row_id": row, "sku": sku.strip() if sku and sku.strip() else None,
            "column": col, "original_value": orig[r, c], "current_value": work[r, c],
            "issue_ids": [i.issue_id for i in related],
            "review_actions": sorted({i.review_action.value for i in related}),
        })
    return {
        "catalogue_id": cat.catalogue_id,
        "changed_cells": changes,
        "unresolved_issues": [i for i in cat.issues if i.status in OPEN],
        "dismissed_issues": [i for i in cat.issues if i.status in DISMISSED],
        "resolved_count": sum(1 for i in cat.issues if i.status == IssueStatus.resolved),
    }
