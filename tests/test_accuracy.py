"""T26: D5 fixed before scoring; wrong/null/missing/failed outputs have known counts."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import test_review_policy


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"


class AccuracyContract(unittest.TestCase):
    setUpGuards = test_review_policy.ReviewPolicyContract.setUp
    tearDown = test_review_policy.ReviewPolicyContract.tearDown

    def setUp(self):
        self.setUpGuards()
        from src.accuracy import score_records
        self.score_records = score_records
        self.expected = json.loads((ROOT / "deliverables/expected-fields.json").read_text())["records"]
        self.rules = json.loads((ROOT / "deliverables/accuracy-rules.json").read_text())
        paths = sorted((ROOT / "materials/requests").glob("*.json")) + [ROOT / "materials/paraphrases/IT-021.json"]
        self.documents = {path.name: self.read_export(path) for path in paths}
        config = json.loads((MOCKS / "evaluation-config.json").read_text())
        self.provider = self.provider_class(MOCKS, replies=config["replies"])
        self.records = self.intake(self.documents.values(), self.provider)

    def score(self, records):
        return self.score_records(records, self.expected, self.documents, self.rules)

    def test_T26_frozen_source_grounded_rules_and_clean_mock_count(self):
        self.assertEqual(len(self.expected), 21)
        self.assertEqual(len(self.rules["fields"]), 12)
        self.assertEqual(self.rules["denominator"], 252)
        for name, expected in self.expected.items():
            self.assertEqual(expected["source_sha256"], self.documents[name].source_sha256)
            self.assertEqual(set(expected["facts"]), set(self.rules["fields"]))
            for quote in expected["evidence"]:
                self.assertIn(quote, self.documents[name].message)
        report = self.score(self.records)
        self.assertEqual((report["matched"], report["total"]), (252, 252))
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["factual_errors"], [])
        self.assertEqual(report["routing_errors"], [])
        self.assertEqual(report["evidence_errors"], [])
        self.assertEqual(report["response_sources"], ["mock"])

    def test_T26_known_wrong_and_unexpected_null_are_one_error_each(self):
        for fixture, actual in (("accuracy-wrong.json", "admin"), ("accuracy-null.json", None)):
            with self.subTest(fixture=fixture):
                provider = self.provider_class(MOCKS, replies={"IT-001.json": fixture})
                wrong = self.intake([self.documents["IT-001.json"]], provider)[0]
                report = self.score([wrong] + self.records[1:])
                self.assertEqual((report["matched"], report["total"]), (251, 252))
                self.assertEqual(len(report["factual_errors"]), 1)
                error = report["factual_errors"][0]
                self.assertEqual(error["document_id"], "IT-001.json")
                self.assertEqual(error["field"], "permission")
                self.assertEqual(error["expected"], "read")
                self.assertEqual(error["actual"], actual)

    def test_T26_missing_invalid_and_failed_records_count_all_twelve_incorrect(self):
        failed_provider = self.provider_class(MOCKS, scripts=json.loads((MOCKS / "persistence-failure.json").read_text()))
        failed = self.intake([self.documents["IT-001.json"]], failed_provider)[0]
        missing_field = deepcopy(self.records[0])
        del missing_field["extraction"]["manager"]
        for records in (self.records[1:], [failed] + self.records[1:], [missing_field] + self.records[1:]):
            with self.subTest(size=len(records)):
                report = self.score(records)
                self.assertEqual((report["matched"], report["total"]), (240, 252))
                self.assertEqual(len(report["factual_errors"]), 12)
        # A failed record with expected nulls earns no null matches.
        failed_null = deepcopy(self.records[2])
        failed_null.update(extraction=None, status="error", error="Simulated failed extraction")
        report = self.score(self.records[:2] + [failed_null] + self.records[3:])
        self.assertEqual((report["matched"], report["total"]), (240, 252))

    def test_T26_exact_comparison_and_unexpected_documents_do_not_change_denominator(self):
        for text in ("maya chen", " Maya Chen", "Maya Chen "):
            candidate = deepcopy(self.records[0])
            candidate["extraction"]["requester"] = text
            report = self.score([candidate] + self.records[1:])
            self.assertEqual(report["matched"], 251)
            self.assertEqual(report["total"], 252)
        unexpected = deepcopy(self.records[0])
        unexpected["document_id"] = "extra.json"
        report = self.score(self.records + [unexpected])
        self.assertEqual(report["unexpected_documents"], ["extra.json"])
        self.assertEqual((report["matched"], report["total"]), (252, 252))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.score(self.records + [self.records[0]])
