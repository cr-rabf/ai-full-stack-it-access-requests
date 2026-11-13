"""T27: parse, compare and reproduce handover artifacts with saved mock replies."""
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_provider_boundary
import test_review_policy


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"


class VerificationContract(unittest.TestCase):
    setUp = test_review_policy.ReviewPolicyContract.setUp
    tearDown = test_review_policy.ReviewPolicyContract.tearDown

    def test_T27_artifacts_redaction_and_reproducible_mock_results(self):
        from src.verification import verify_artifacts
        from src.provider import AnthropicProvider

        report = verify_artifacts(ROOT)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["documents"], 21)
        self.assertEqual(report["scalar_matches"], 252)
        self.assertEqual(report["response_sources"], ["mock"])

        document = self.read_export(ROOT / "materials/requests/IT-001.json")
        provider = AnthropicProvider(transport=test_provider_boundary.SavedHTTPTransport([
            "provider-complete-001.json"]), credential_loader=mock.Mock(return_value=test_provider_boundary.FAKE_SECRET))
        reply = provider.extract(document.document_id, document.message)
        self.assertEqual(reply["response_source"], "mock")
        self.assertEqual(json.loads(reply["output_text"])["requester"], "Maya Chen")
        evidence = json.loads((ROOT / "deliverables/request-evidence.json").read_text())
        actual = provider.request_evidence(document)
        for field, value in actual.items():
            self.assertEqual(evidence[field], value, field)
        self.assertNotIn(test_provider_boundary.FAKE_SECRET, json.dumps(evidence))

        config = json.loads((MOCKS / "evaluation-config.json").read_text())
        provider = self.provider_class(MOCKS, replies=config["replies"])
        paths = sorted((ROOT / "materials/requests").glob("*.json")) + [ROOT / "materials/paraphrases/IT-021.json"]
        first = self.intake([self.read_export(path) for path in paths], provider)
        second = self.intake([self.read_export(path) for path in paths], provider)
        self.assertEqual(first, second)
        generation = (ROOT / "deliverables/current").resolve()
        committed = {r["document_id"]: r for r in map(json.loads,
                     (generation / "extractions.jsonl").read_text().splitlines())}
        for record in first:
            saved = committed[record["document_id"]]
            for field in ("source_sha256", "extraction", "status", "owner", "next_action", "error", "response_source"):
                self.assertEqual(saved[field], record[field], (record["document_id"], field))

        # Retry guidance must retain a nondefault database and mocked provider;
        # otherwise copying it would target different state or a real model.
        from src.cli import main
        with tempfile.TemporaryDirectory() as directory:
            arguments = ["--db", str(Path(directory) / "state.sqlite3"), "--mock-config",
                         str(MOCKS / "cli-outage.json"), "intake", str(ROOT / "materials/requests/IT-002.json")]
            output = io.StringIO()
            with mock.patch("sys.stdout", output):
                self.assertEqual(main(arguments), 1)
            failure, = json.loads(output.getvalue())
            self.assertEqual(failure["retry_arguments"], arguments[:4] + ["retry", "--document", "IT-002.json"])
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(main(failure["retry_arguments"]), 1)
