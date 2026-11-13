"""Check complete, independently authored facts and source evidence.

This is an acceptance checker, not the accuracy scorer. Corpus normalization,
denominators and failed-output counting remain subject to decision D5.
"""

from .review import SCALARS
from .validation import validate_extraction


def check_expected(message, expected, result):
    """Reject incomplete expectations before comparing an intake record with them.

    Source evidence establishes quote membership; semantic review of the authored
    expected facts remains a human task. Mock replies do not establish accuracy.
    """
    if not isinstance(expected, dict):
        raise ValueError("Expected record must be an object")
    for group in ("facts", "evidence", "route"):
        if not isinstance(expected.get(group), dict):
            raise ValueError(f"Expected record requires {group}")
    for group in ("facts", "evidence"):
        for field in SCALARS:
            if field not in expected[group]:
                raise ValueError(f"Expected {group} missing {field}")
        if set(expected[group]) != set(SCALARS):
            raise ValueError(f"Expected {group} has unknown fields")
    for field, quote in expected["evidence"].items():
        if not isinstance(quote, str) or not quote or quote not in message:
            raise ValueError(f"Expected evidence for {field} must be an exact source quote")
    validate_extraction(dict(expected["facts"],
                             supporting_quotes=list(expected["evidence"].values()), issues=[]), message)
    route_fields = ("status", "owner", "next_action")
    if set(expected["route"]) != set(route_fields):
        raise ValueError("Expected route requires status, owner and next_action")
    differences = []
    extraction = result.get("extraction") or {}
    for field, value in expected["facts"].items():
        if field not in extraction or extraction[field] != value:
            differences.append({"field": field, "expected": value, "actual": extraction.get(field)})
    for field in route_fields:
        value = expected["route"][field]
        if result.get(field) != value:
            differences.append({"field": field, "expected": value, "actual": result.get(field)})
    return {"matches": not differences, "differences": differences}
