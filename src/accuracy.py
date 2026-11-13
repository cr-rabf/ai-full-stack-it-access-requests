"""Source-grounded scalar evaluation using the human-approved, frozen D5 rules."""

import hashlib
import json
from pathlib import Path

from .validation import validate_extraction


def score_records(records, expected, documents, rules):
    fields = rules["fields"]
    if len(expected) != rules["documents"] or len(fields) * len(expected) != rules["denominator"]:
        raise ValueError("Frozen document/field counts do not match the denominator")
    indexed = {}
    for record in records:
        name = record["document_id"]
        if name in indexed:
            raise ValueError(f"duplicate document_id: {name}")
        indexed[name] = record
    errors, routing_errors, evidence_errors = [], [], []
    matched = 0
    for name, expectation in expected.items():
        if name not in documents or expectation["source_sha256"] != documents[name].source_sha256:
            raise ValueError(f"Expected source identity does not match: {name}")
        if set(expectation["facts"]) != set(fields):
            raise ValueError(f"Incomplete frozen facts: {name}")
        message = documents[name].message
        for quote in expectation["evidence"]:
            if not quote or quote not in message:
                raise ValueError(f"Invented expected evidence: {name}")
        record = indexed.get(name)
        reason = None
        extraction = None
        if record is None:
            reason = "missing document"
        elif record.get("status") not in ("review", "needs-information") or record.get("error") is not None:
            reason = "failed or unfinished extraction"
        elif record.get("source_sha256") != expectation["source_sha256"]:
            reason = "source identity mismatch"
        else:
            extraction = record.get("extraction")
            try:
                validate_extraction(extraction, message)
            except ValueError:
                reason = "invalid extraction"
        for field in fields:
            target = expectation["facts"][field]
            actual = extraction.get(field) if isinstance(extraction, dict) else None
            if reason is None and field in extraction and actual == target:
                matched += 1
            else:
                errors.append({"document_id": name, "field": field, "expected": target,
                               "actual": actual, "reason": reason or "value mismatch"})
        if record:
            for field, value in expectation["route"].items():
                if record.get(field) != value:
                    routing_errors.append({"document_id": name, "field": field,
                                           "expected": value, "actual": record.get(field)})
        if isinstance(extraction, dict):
            quotes = extraction.get("supporting_quotes", [])
            if not isinstance(quotes, list) or not all(isinstance(quote, str) for quote in quotes):
                quotes = []
            for quote in expectation["evidence"]:
                if not any(quote in supplied for supplied in quotes):
                    evidence_errors.append({"document_id": name, "missing_evidence": quote})
    total = rules["denominator"]
    configs = {json.dumps(record.get("provider_config", {}), sort_keys=True) for record in records}
    return {
        "matched": matched, "total": total, "accuracy": matched / total,
        "factual_errors": errors, "routing_errors": routing_errors, "evidence_errors": evidence_errors,
        "unexpected_documents": sorted(set(indexed) - set(expected)),
        "response_sources": sorted({record.get("response_source", "unknown") for record in records}),
        "provider_configurations": [json.loads(config) for config in sorted(configs)],
    }


def write_report(path, report, expected, expected_path, rules_path):
    expected_hash = hashlib.sha256(Path(expected_path).read_bytes()).hexdigest()
    rules_hash = hashlib.sha256(Path(rules_path).read_bytes()).hexdigest()
    lines = [
        "# Source-grounded accuracy evaluation", "",
        "Observed configuration: saved mock responses from `tests/mock_responses/evaluation-config.json`.",
        "These observations exercise fixture plumbing and deterministic policy, not live model accuracy.",
        "The Anthropic HTTP adapter is separately contract-tested through fake transport; no live call was made.", "",
        "Rules approved by the user and frozen before scoring: 12 scalar fields × 21 messages = 252 comparisons.",
        "Strings compare exactly, including case and whitespace. Dates have no additional normalization.",
        "A successful explicit null matches only an expected null. Missing documents and failed, unfinished,",
        "source-mismatched or schema-invalid records receive zero of 12 matches, even for expected nulls.",
        "Unexpected documents are reported separately; they do not change the denominator. Routing and",
        "evidence checks are separate and do not increase the accuracy denominator.", "",
        f"Observed scalar matches: **{report['matched']}/{report['total']} ({report['accuracy']:.2%})**.",
        f"Factual errors: {len(report['factual_errors'])}; routing differences: {len(report['routing_errors'])}; "
        f"evidence differences: {len(report['evidence_errors'])}.",
        f"Unexpected documents: {json.dumps(report['unexpected_documents'])}.", "",
        f"Frozen expectation SHA-256: `{expected_hash}`.", f"Frozen rules SHA-256: `{rules_hash}`.", "",
        "Reproduce from the repository root after mocked intake of the corpus and paraphrase:", "",
        "```bash", "env -u API_KEY python3 -m access_request accuracy --records deliverables/extractions.jsonl --report deliverables/accuracy.md", "```", "",
        "Expected fields below were transferred from the independent F001–F021 source ledger before scorer",
        "implementation. [expected-fields.json](expected-fields.json) contains every exact evidence quote,",
        "source hash and expected route. [accuracy-rules.json](accuracy-rules.json) contains the frozen rules.",
        "Null expectations reflect review of the full source and policy; a short quote alone cannot prove absence.", "",
        "| Document | Expected scalar facts |", "|---|---|",
    ]
    for name, expectation in expected.items():
        facts = "; ".join(f"`{field}={json.dumps(value, ensure_ascii=False)}`"
                          for field, value in expectation["facts"].items())
        lines.append(f"| {name} | {facts} |")
    lines += ["", "Detailed observations and factual differences:", "", "```json",
              json.dumps(report, indent=2), "```", "",
              "The hand-authored mocks encode known facts. Their match rate does not establish extraction",
              "quality on fresh live responses, generalization, provider latency or throughput.", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
