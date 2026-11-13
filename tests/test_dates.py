"""R-27: source-grounded dates, strict representations and calendar boundaries.

The corpus expectations come from the independent F001–F021 ledger. Synthetic
values below are authored calendar/format cases, not values discovered in a run.
Negative cases verify that intake flags invalid dates for clarification; the
original invalid value remains visible for human review.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import test_review_policy


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"
FIELDS = ("request_date", "start_date", "end_date")
VALID = ("2024-02-29", "2000-02-29", "0001-01-01", "9999-12-31", "2026-10-23")
INVALID = (
    "10/23/2026", "2026-1-2", "20261023", "2026-W43-5", "2026-10-23T00:00:00Z",
    " 2026-10-23", "2026-10-23 ", "2026-02-30", "2025-02-29", "1900-02-29",
    "2026-13-01", "2026-00-01", "2026-01-00", "2026-04-31", "0000-01-01",
    "next Monday", "",
)


class DateContract(unittest.TestCase):
    setUp = test_review_policy.ReviewPolicyContract.setUp
    tearDown = test_review_policy.ReviewPolicyContract.tearDown

    def test_R27_all_corpus_dates_match_source_expectations_and_calendar_format(self):
        expected = json.loads((ROOT / "deliverables/expected-fields.json").read_text())["records"]
        config = json.loads((MOCKS / "evaluation-config.json").read_text())
        paths = sorted((ROOT / "materials/requests").glob("*.json")) + [ROOT / "materials/paraphrases/IT-021.json"]
        documents = [self.read_export(path) for path in paths]
        provider = self.provider_class(MOCKS, replies=config["replies"])
        records = self.intake(documents, provider)
        self.assertEqual(len(records), 21)
        for record in records:
            self.assertEqual(record["response_source"], "mock")
            self.assertIsNone(record["error"])
            extraction = record["extraction"]
            for field in FIELDS:
                with self.subTest(document=record["document_id"], field=field):
                    value = extraction[field]
                    self.assertEqual(value, expected[record["document_id"]]["facts"][field])
                    if value is None:
                        self.assertTrue(any(field in issue for issue in extraction["issues"]))
                    else:
                        self.assertRegex(value, r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
                        date(int(value[:4]), int(value[5:7]), int(value[8:10]))

    def run_date_case(self, key, dates):
        saved = json.loads((MOCKS / "date-validation-cases.json").read_text())
        # Author source text independently of the mock payload; verify every
        # date field against the explicit test inputs, not fixture-derived values.
        facts = {
            "request_id": "IT-001", "request_date": "2026-10-22", "kind": "new",
            "requester": "Maya Chen", "team": "Analytics", "system": "Atlas",
            "environment": "staging", "permission": "read",
            "business_purpose": "checking the weekly conversion dashboard with the new event definition changes",
            "start_date": "2026-10-23", "end_date": "2026-11-06", "manager": "Priya Shah",
        }
        facts.update(dates)
        message = " ".join(f"{field}: {value}." for field, value in facts.items())
        document = self.read_export(ROOT / "materials/requests/IT-001.json")
        document = replace(document, message=message)
        provider = SimpleNamespace(response_source="mock", extract=mock.Mock(return_value=deepcopy(saved[key])))
        result, = self.intake([document], provider)
        provider.extract.assert_called_once_with("IT-001.json", message)
        self.assertEqual(result["response_source"], "mock")
        self.assertIsNone(result["error"])
        for field in FIELDS:
            self.assertEqual(result["extraction"][field], facts[field])
        return result

    def test_R27_valid_leap_days_and_calendar_boundaries_are_accepted(self):
        for number, value in enumerate(VALID):
            with self.subTest(value=value):
                result = self.run_date_case(f"valid-{number}", dict.fromkeys(FIELDS, value))
                self.assertEqual(result["extraction"]["issues"], [])
                self.assertEqual(result["status"], "review")
                self.assertEqual(result["owner"], "System Owner")

    def test_R27_each_invalid_format_or_calendar_date_is_flagged_in_every_date_field(self):
        for field in FIELDS:
            for number, value in enumerate(INVALID):
                with self.subTest(field=field, value=value):
                    result = self.run_date_case(f"{field}-invalid-{number}", {field: value})
                    self.assertEqual(result["status"], "needs-information")
                    self.assertEqual(result["owner"], "IT Service Desk")
                    self.assertEqual(result["next_action"], "clarify")
                    self.assertIn(f"Invalid {field}; use YYYY-MM-DD.", result["extraction"]["issues"])

    def test_R27_reversed_dates_have_valid_format_but_separate_order_issue(self):
        document = self.read_export(ROOT / "materials/requests/IT-014.json")
        provider = self.provider_class(MOCKS, replies={"IT-014.json": "reversed-014.json"})
        result, = self.intake([document], provider)
        extraction = result["extraction"]
        self.assertEqual(extraction["start_date"], "2026-11-05")
        self.assertEqual(extraction["end_date"], "2026-11-02")
        self.assertEqual(result["status"], "needs-information")
        self.assertIn("start_date is after end_date.", extraction["issues"])
        self.assertFalse(any(issue.startswith("Invalid ") for issue in extraction["issues"]))
