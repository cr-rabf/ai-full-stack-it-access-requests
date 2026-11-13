"""Validate the supplied extraction schema and exact source evidence before routing."""

import json
from pathlib import Path


_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "snapshot.schema.json").read_text(encoding="utf-8")
)


def validate_extraction(candidate: object, message: str) -> None:
    """Enforce snapshot.schema.json's object, scalar, enum and string-array rules.

    This checks structure and quote membership. Source-fact interpretation and
    review policy are separate from schema validation.
    """
    if not isinstance(candidate, dict):
        raise ValueError("Extraction must be an object")
    for field in _SCHEMA["required"]:
        if field not in candidate:
            raise ValueError(f"Extraction is missing required property: {field}")
    if _SCHEMA["additionalProperties"] is False:
        if any(field not in _SCHEMA["properties"] for field in candidate):
            raise ValueError("Extraction contains an unknown property")

    for field, rule in _SCHEMA["properties"].items():
        value = candidate[field]
        if rule["type"] == "array":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{field} must be an array of strings")
        else:
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be a string or null")
            if "enum" in rule and value not in rule["enum"]:
                raise ValueError(f"{field} is not an allowed enum value")

    if not isinstance(message, str):
        raise ValueError("Source message must be a string")
    for quote in candidate["supporting_quotes"]:
        if quote not in message:
            raise ValueError("supporting_quotes must be exact substrings of the decoded message")


def validate_and_route(candidate: object, message: str, router):
    """Only hand a schema-valid, source-quoted extraction to the supplied router."""
    validate_extraction(candidate, message)
    return router(candidate)
