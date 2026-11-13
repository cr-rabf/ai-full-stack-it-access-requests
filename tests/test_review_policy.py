"""T08–T15: independent plan facts, saved responses, ordered human review rules."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import unittest
from unittest import mock

from test_mock_provider import NoCredentials


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"
EXPECTED = json.loads((ROOT / "tests/expectations/source_facts.json").read_text())
ROUTES = {
    "Owner": ("review", "System Owner", "review-request"),
    "Security": ("review", "Security Review", "review-risk-then-owner"),
    "Desk clarify": ("needs-information", "IT Service Desk", "clarify"),
    "Inspect": ("review", "IT Service Desk", "inspect-message"),
    "Withdraw": ("review", "IT Service Desk", "confirm-withdrawal"),
}


class ReviewPolicyContract(unittest.TestCase):
    def setUp(self):
        self.network = mock.Mock(side_effect=AssertionError("network access forbidden"))
        for patcher in (mock.patch.object(socket, "socket", self.network),
                        mock.patch.object(socket, "create_connection", self.network),
                        mock.patch.object(os, "environ", NoCredentials())):
            patcher.start()
            self.addCleanup(patcher.stop)
        from src.exports import read_export
        from src.mock_provider import MockProvider
        from src.review import intake, route
        self.read_export = read_export
        self.provider_class = MockProvider
        self.intake = intake
        self.route = route

    def tearDown(self):
        self.network.assert_not_called()

    def source(self, number):
        return self.read_export(ROOT / f"materials/requests/IT-{number:03d}.json")

    def run_saved(self, document, fixture):
        provider = self.provider_class(MOCKS, replies={document.document_id: fixture})
        result, = self.intake([document], provider)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result["document_id"], document.document_id)
        self.assertEqual(result["source_sha256"], document.source_sha256)
        self.assertEqual(result["response_source"], "mock")
        self.assertIsNone(result["error"])
        self.assertNotIn("approved", (result["status"], result["next_action"]))
        return result

    def assert_route(self, result, name):
        self.assertEqual(tuple(result[field] for field in ("status", "owner", "next_action")),
                         ROUTES[name])
        self.assertIn("human", result["review_note"].lower())
        self.assertIn("contact", result["review_note"].lower())

    def case(self, number):
        document = self.source(number)
        expected = EXPECTED[document.document_id]
        result = self.run_saved(document, expected["fixture"])
        extraction = result["extraction"]
        for field, value in expected["facts"].items():
            self.assertEqual(extraction[field], value, (document.document_id, field))
            if value is None:
                self.assertTrue(any(field in issue for issue in extraction["issues"]), field)
        for quote in extraction["supporting_quotes"]:
            self.assertIn(quote, document.message)
        for evidence in expected["evidence"]:
            self.assertTrue(any(evidence in quote for quote in extraction["supporting_quotes"]), evidence)
        self.assert_route(result, expected["route"])
        return result

    def test_T08_complete_request(self):
        result = self.case(1)
        self.assertEqual(result["extraction"]["issues"], [])

    def test_T09_missing_and_relative_dates_precede_risk(self):
        for number in (10, 11):
            with self.subTest(number=number):
                self.case(number)

    def test_T10_conflicting_alternatives_are_unresolved_and_quoted(self):
        for number in (4, 20):
            with self.subTest(number=number):
                result = self.case(number)
                self.assertIn("conflict", " ".join(result["extraction"]["issues"]).lower())

    def test_T11_override_precedes_withdrawal_and_preserves_evidence(self):
        original = self.case(6)
        self.assertEqual(original["extraction"]["permission"], "read")
        self.assertIn("override", " ".join(original["extraction"]["issues"]).lower())
        document = self.source(6)
        message = document.message + " Please withdraw IT-006. Date: 2026-10-22."
        document = replace(document, message=message)
        result = self.run_saved(document, "override-withdrawal.json")
        self.assert_route(result, "Inspect")
        # Even a withdrawal extraction must retain the higher-priority override.
        candidate = deepcopy(result["extraction"])
        candidate["kind"] = "withdrawal"
        self.assert_route(self.route(candidate, document), "Inspect")

    def test_T12_corrections_and_requested_new_permissions(self):
        for number in (7, 8, 15, 19):
            with self.subTest(number=number):
                result = self.case(number)
                self.assertEqual(result["extraction"]["issues"], [])

    def test_T13_withdrawal_precedes_missing_fields(self):
        self.case(5)
        document = replace(self.source(5), message="Please withdraw IT-005. Date: 2026-10-22.")
        result = self.run_saved(document, "withdrawal-minimal.json")
        self.assert_route(result, "Withdraw")
        for field in ("requester", "team", "system", "environment", "permission",
                      "business_purpose", "start_date", "end_date", "manager"):
            self.assertIsNone(result["extraction"][field])
            self.assertTrue(any(field in issue for issue in result["extraction"]["issues"]))

    def test_T14_clarification_matrix_and_independent_documents(self):
        for number in (3, 9, 14, 16, 17):
            with self.subTest(number=number):
                self.case(number)
        required = ("request_id", "request_date", "requester", "team", "system",
                    "environment", "permission", "business_purpose", "start_date", "end_date", "manager")
        base = json.loads(json.loads((MOCKS / "required-null.json").read_text())["output_text"])
        clauses = {
            "request_id": "Request IT-001.", "request_date": "Request date: 2026-10-22.",
            "kind": "Kind: new.", "requester": "Requester: Maya Chen.", "team": "Team: Analytics.",
            "system": "System: Atlas.", "environment": "Environment: staging.", "permission": "Permission: read.",
            "business_purpose": "Business purpose: checking the weekly conversion dashboard.",
            "start_date": "Start date: 2026-10-23.", "end_date": "End date: 2026-11-06.",
            "manager": "Manager: Priya Shah.",
        }
        for kind in ("new", "change"):
            for field in required + ("kind",):
                with self.subTest(kind=kind, missing=field):
                    candidate = deepcopy(base)
                    candidate["kind"] = kind
                    candidate[field] = None
                    # Deliberately omit the issue to verify deterministic validation adds it.
                    candidate["issues"] = []
                    evidence = [text.replace("Kind: new.", f"Kind: {kind}.")
                                for name, text in clauses.items() if name != field]
                    candidate["supporting_quotes"] = evidence
                    document = replace(self.source(1), message=" ".join(evidence))
                    result = self.route(candidate, document)
                    self.assert_route(result, "Desk clarify")
                    self.assertTrue(any(field in issue for issue in candidate["issues"]))
        mismatch = self.source(16)
        matching = replace(mismatch, document_id="IT-061.json")
        provider = self.provider_class(MOCKS, replies={
            "IT-016.json": "duplicate-id.json", "IT-061.json": "duplicate-id.json"})
        results = self.intake([mismatch, matching], provider)
        self.assertEqual([r["document_id"] for r in results], ["IT-016.json", "IT-061.json"])
        self.assert_route(results[0], "Desk clarify")
        self.assert_route(results[1], "Owner")
        for result in results:
            self.assertEqual(result["extraction"]["request_id"], "IT-061")
        self.assertIn("mismatch", " ".join(results[0]["extraction"]["issues"]).lower())
        reversed_candidate = deepcopy(base)
        reversed_candidate.update(start_date="2026-11-05", end_date="2026-11-02", issues=[])
        self.assert_route(self.route(reversed_candidate, self.source(1)), "Desk clarify")
        self.assertTrue(any("start_date" in issue and "end_date" in issue
                            for issue in reversed_candidate["issues"]))

    def test_T15_risk_matrix_and_human_decisions(self):
        for number in (2, 7, 12, 13):
            with self.subTest(number=number):
                result = self.case(number)
                self.assertIn("recommendation", result["review_note"].lower())
                self.assertIn("system owner", result["review_note"].lower())
        document = self.source(7)
        document = replace(document, message=document.message.replace("transition to (write)",
                           "transition to (read)").replace("current (read only)", "current (write)"))
        result = self.run_saved(document, "change-read-staging.json")
        self.assert_route(result, "Owner")
        self.assertEqual(result["extraction"]["kind"], "change")
        self.assertEqual(result["extraction"]["permission"], "read")
