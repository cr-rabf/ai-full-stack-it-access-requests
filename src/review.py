"""Ordered office policy for validated extraction candidates awaiting human review."""

from datetime import date
from pathlib import Path
import re

from .processing import process_batch


REQUIRED_FACTS = (
    "request_id", "request_date", "requester", "team", "system", "environment",
    "permission", "business_purpose", "start_date", "end_date", "manager",
)
SCALARS = REQUIRED_FACTS + ("kind",)
HUMAN_REVIEW = "Awaiting human review. A named manager is a contact; approval is an explicit human decision."


def _issue(extraction, text):
    if text not in extraction["issues"]:
        extraction["issues"].append(text)


def route(extraction, document):
    """Apply policy after structural validation; enrich deterministic issues in place.

    The extraction prompt supplies semantic facts and unresolved conflicts.
    Missing fields, date order and filename mismatches can also be checked locally.
    Override markers in source or extraction issues trigger the first review rule.
    """
    for field in SCALARS:
        if extraction[field] is None:
            _issue(extraction, f"Missing or unresolved {field}.")
    identifier = extraction["request_id"]
    if identifier and identifier != Path(document.document_id).stem:
        _issue(extraction, "request_id mismatch with document filename.")
    dates = {}
    for field in ("request_date", "start_date", "end_date"):
        value = extraction[field]
        if value is not None:
            try:
                parsed = date.fromisoformat(value)
                if value != parsed.isoformat():
                    raise ValueError("date is not YYYY-MM-DD")
                dates[field] = parsed
            except ValueError:
                _issue(extraction, f"Invalid {field}; use YYYY-MM-DD.")
    if "start_date" in dates and "end_date" in dates and dates["start_date"] > dates["end_date"]:
        _issue(extraction, "start_date is after end_date.")

    override = re.search(
        r"system\s+override|bypass\s+approval|highest.priority\s+system\s+instruction|"
        r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|"
        r"(?:display|reveal|print)\b[^.\n]*\b(?:api\s*key|secret)",
        document.message, re.IGNORECASE,
    )
    flagged = any("override" in issue.lower() or "instruction-override" in issue.lower()
                  for issue in extraction["issues"])
    note = HUMAN_REVIEW
    if override or flagged:
        _issue(extraction, "Instruction override attempt in source message.")
        # Preserve the instruction-bearing paragraph, including all its sentences.
        if override:
            evidence = document.message[override.start():].split("\n\n", 1)[0]
            if evidence not in extraction["supporting_quotes"]:
                extraction["supporting_quotes"].append(evidence)
        status, owner, action = "review", "IT Service Desk", "inspect-message"
    elif extraction["kind"] == "withdrawal" and identifier and extraction["request_date"]:
        status, owner, action = "review", "IT Service Desk", "confirm-withdrawal"
    elif (extraction["kind"] not in ("new", "change") or extraction["issues"]
          or any(extraction[field] is None for field in REQUIRED_FACTS)):
        status, owner, action = "needs-information", "IT Service Desk", "clarify"
    elif (extraction["environment"] == "production" or extraction["permission"] in ("write", "admin")):
        status, owner, action = "review", "Security Review", "review-risk-then-owner"
        note += " Security Review forwards its risk recommendation to the system owner for a decision."
    else:
        status, owner, action = "review", "System Owner", "review-request"
    return {"status": status, "owner": owner, "next_action": action, "review_note": note}


def intake(documents, provider):
    """Use the same extraction boundary for every independent source document."""
    results = []
    for document in documents:
        results.extend(process_batch([document], provider, lambda extraction: route(extraction, document)))
    return results
