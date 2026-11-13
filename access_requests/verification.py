"""Check handover artifacts against source identity, schema, frozen facts and adapter."""

import argparse
import hashlib
import json
from pathlib import Path

from .accuracy import score_records
from .exports import read_export
from .provider import AnthropicProvider


def verify_artifacts(root):
    root = Path(root).resolve()
    deliverables = root / "deliverables"
    generation = (deliverables / "current").resolve(strict=True)
    if generation.parent != deliverables / "generations":
        raise ValueError("Current generation is outside the deliverables snapshot directory")
    records = [json.loads(line) for line in (generation / "extractions.jsonl").read_text().splitlines()]
    queue = json.loads((generation / "queue.json").read_text())
    history = [json.loads(line) for line in (generation / "history.jsonl").read_text().splitlines()]
    expected_path = deliverables / "expected-fields.json"
    rules_path = deliverables / "accuracy-rules.json"
    expected = json.loads(expected_path.read_text())["records"]
    rules = json.loads(rules_path.read_text())
    paths = sorted((root / "materials/requests").glob("*.json")) + [root / "materials/paraphrases/IT-021.json"]
    documents = {path.name: read_export(path) for path in paths}
    score = score_records(records, expected, documents, rules)
    errors = []
    if (score["factual_errors"] or score["routing_errors"] or score["evidence_errors"]
            or score["unexpected_documents"]):
        errors.append("Current records differ from source-grounded expectations")
    by_document = {record["document_id"]: record for record in records}
    if len(queue) != len(records) or len({r["document_id"] for r in queue}) != len(records):
        errors.append("Queue document identities are not unique and complete")
    for item in queue:
        record = by_document.get(item["document_id"], {})
        for field in ("attempt_id", "source_sha256", "generation_id", "status", "owner", "next_action", "error"):
            if item.get(field) != record.get(field):
                errors.append(f"Queue/extraction mismatch: {item['document_id']} {field}")
        if item.get("generation_id") != generation.name:
            errors.append("Generation identity does not match the pinned snapshot")
    historical = {(record["document_id"], record["attempt_id"], record["source_sha256"]) for record in history}
    for record in records:
        if (record["document_id"], record["attempt_id"], record["source_sha256"]) not in historical:
            errors.append(f"Missing current attempt in history: {record['document_id']}")
        for key, path in (("prompt_sha256", root / "access_requests/extraction_prompt.txt"),
                          ("schema_sha256", root / "snapshot.schema.json"),
                          ("policy_sha256", root / "materials/office-policy.md"),
                          ("routing_sha256", root / "access_requests/review.py")):
            if record["processing_settings"].get(key) != hashlib.sha256(path.read_bytes()).hexdigest():
                errors.append(f"Processing provenance differs: {record['document_id']} {key}")
    evidence = json.loads((deliverables / "request-evidence.json").read_text())
    # Construct the implemented request without loading a credential or making a call.
    transport = type("MockTransportIdentity", (), {"response_source": "mock"})()
    provider = AnthropicProvider(transport=transport)
    actual = provider.request_evidence(documents["IT-001.json"])
    for field, value in actual.items():
        if evidence.get(field) != value:
            errors.append(f"Request evidence differs from implemented adapter: {field}")
    if evidence.get("headers", {}).get("Authorization") != "[REDACTED]":
        errors.append("Request credential header is not redacted")
    accuracy = (deliverables / "accuracy.md").read_text()
    for path in (expected_path, rules_path):
        if hashlib.sha256(path.read_bytes()).hexdigest() not in accuracy:
            errors.append("Accuracy report does not identify the frozen artifact hashes")
    verification = (deliverables / "verification.md").read_text()
    for required in ("Observed", "Intended", "C1", "C2", "C3", "mock", "2,000", "interruption"):
        if required not in verification:
            errors.append(f"Verification documentation missing {required}")
    return {"passed": not errors, "documents": len(records), "scalar_matches": score["matched"],
            "response_sources": score["response_sources"], "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = verify_artifacts(args.root)
    print(json.dumps(result, indent=2))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
