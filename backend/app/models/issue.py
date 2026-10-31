"""Pydantic models for the issue ledger.

An issue keeps three values conceptually separate:
  original_value  - what was uploaded (never changes)
  proposed_value  - what the system suggests, only when the fix is clear
  current_value   - the value in the working copy right now
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class IssueStatus(str, Enum):
    open = "open"
    ready_for_review = "ready_for_review"
    needs_investigation = "needs_investigation"
    accepted = "accepted"
    edited = "edited"
    rejected = "rejected"
    ignored = "ignored"
    resolved = "resolved"


class ReviewAction(str, Enum):
    accept = "accept"
    edit = "edit"
    reject = "reject"
    ignore = "ignore"
    undo = "undo"


class IssueType(str, Enum):
    missing_required = "missing_required"
    missing_optional = "missing_optional"
    duplicate_sku = "duplicate_sku"
    invalid_number = "invalid_number"
    negative_price = "negative_price"
    zero_price = "zero_price"
    negative_stock = "negative_stock"
    non_integer_stock = "non_integer_stock"
    malformed_url = "malformed_url"
    whitespace = "whitespace"
    inconsistent_format = "inconsistent_format"
    category_mapping = "category_mapping"
    missing_currency = "missing_currency"
    invalid_currency = "invalid_currency"


class Issue(BaseModel):
    issue_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    row_id: int = Field(description="0-based row position in the uploaded file")
    sku: str | None = None
    column: str = Field(description="Original CSV column name")
    original_value: str
    current_value: str
    issue_type: IssueType
    severity: Severity
    explanation: str
    proposed_value: str | None = None
    status: IssueStatus = IssueStatus.open
    review_action: ReviewAction | None = None
    # After accept/edit: did revalidation of the new value pass? None = not applicable.
    revalidation_passed: bool | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
