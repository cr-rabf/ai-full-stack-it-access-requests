"""T02/T03: source identity, export boundary, strict schema and exact quotes.

Expected facts below come from F001/F021 and the schema in planning/plan.md,
independently of the saved mock payloads under tests/mock_responses/.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from test_mock_provider import NoCredentials


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"
SCALARS = (
    "request_id", "request_date", "kind", "requester", "team", "system",
    "environment", "permission", "business_purpose", "start_date", "end_date", "manager",
)
REQUIRED = SCALARS + ("supporting_quotes", "issues")


class ExportValidationContract(unittest.TestCase):
    def setUp(self):
        self.network = mock.Mock(side_effect=AssertionError("network access forbidden"))
        for patcher in (
            mock.patch.object(socket, "socket", self.network),
            mock.patch.object(socket, "create_connection", self.network),
            mock.patch.object(os, "environ", NoCredentials()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        from access_requests.exports import read_export
        from access_requests.validation import validate_extraction, validate_and_route
        from access_requests.mock_provider import MockProvider

        self.read_export = read_export
        self.validate = validate_extraction
        self.validate_and_route = validate_and_route
        self.provider = MockProvider(MOCKS, replies={
            "IT-001.json": "complete-001.json",
            "IT-021.json": "boundary-200.json",
            "invalid.json": "schema-invalid.json",
        })
        self.raw = (ROOT / "materials/requests/IT-001.json").read_bytes()
        self.source = json.loads(self.raw)
        self.message = self.source["message"]
        self.candidate = self.reply("IT-001.json", self.message)

    def tearDown(self):
        self.network.assert_not_called()

    def reply(self, document_id, message):
        return json.loads(self.provider.extract(document_id, message)["output_text"])

    def test_T02_original_bytes_filename_and_decoded_message(self):
        for filename, raw in (
            ("IT-001.json", self.raw),
            ("new-export-name.json", b"\n" + self.raw + b"  "),
        ):
            with self.subTest(filename=filename):
                path = self.directory / filename
                path.write_bytes(raw)
                document = self.read_export(path)
                self.assertEqual(document.document_id, filename)
                self.assertEqual(document.raw_bytes, raw)
                self.assertEqual(document.source_sha256, hashlib.sha256(raw).hexdigest())
                self.assertEqual(document.message, self.message)
                self.assertNotEqual(document.document_id, "IT-001")
                for quote in self.candidate["supporting_quotes"]:
                    self.assertIn(quote, document.message)
        self.assertNotEqual(
            self.read_export(self.directory / "IT-001.json").source_sha256,
            self.read_export(self.directory / "new-export-name.json").source_sha256,
        )

    def test_T02_misleading_metadata_supplies_no_request_facts(self):
        source = dict(self.source, exported_at="2030-01-01T00:00:00Z",
                      subject="Production admin request")
        path = self.directory / "IT-001.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        document = self.read_export(path)
        candidate = self.reply(document.document_id, document.message)
        self.validate(candidate, document.message)
        self.assertEqual(document.message, self.message)
        self.assertEqual(candidate["request_date"], "2026-10-22")
        self.assertEqual(candidate["environment"], "staging")
        self.assertEqual(candidate["permission"], "read")

    def test_T02_exact_200_word_export_and_response(self):
        raw = (ROOT / "tests/fixtures/boundary-200-export.json").read_bytes()
        path = self.directory / "IT-021.json"
        path.write_bytes(raw)
        document = self.read_export(path)
        self.assertEqual(len(document.message.split()), 200)
        self.assertEqual(document.document_id, "IT-021.json")
        self.assertEqual(document.raw_bytes, raw)
        candidate = self.reply(document.document_id, document.message)
        self.validate(candidate, document.message)
        expected = (
            "IT-021", "2026-10-22", "new", "Maya Chen", "Analytics", "Atlas",
            "staging", "read", "check weekly conversion dashboard totals",
            "2026-10-23", "2026-11-06", "Priya Shah",
        )
        self.assertEqual(tuple(candidate[field] for field in SCALARS), expected)
        self.assertEqual(candidate["issues"], [])

    def test_T02_malformed_exports_are_rejected(self):
        for raw in (b"not JSON", b"[]", b"{}", b'{"message": null}',
                    b'{"message": 42}', b'{"message": "\xff"}'):
            with self.subTest(raw=raw):
                path = self.directory / "broken.json"
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.read_export(path)

    def assert_rejected_before_routing(self, candidate):
        router = mock.Mock()
        with self.assertRaises(ValueError):
            self.validate_and_route(candidate, self.message, router)
        router.assert_not_called()

    def test_T03_valid_objects_and_each_nullable_scalar(self):
        self.validate(self.candidate, self.message)
        for field in SCALARS:
            with self.subTest(field=field):
                candidate = deepcopy(self.candidate)
                candidate[field] = None
                candidate["issues"] = [f"Missing {field}."]
                self.validate(candidate, self.message)
        router = mock.Mock(return_value="routed")
        self.assertEqual(self.validate_and_route(self.candidate, self.message, router), "routed")
        router.assert_called_once_with(self.candidate)

    def test_T03_all_properties_required_and_no_unknown_properties(self):
        for field in REQUIRED:
            with self.subTest(missing=field):
                candidate = deepcopy(self.candidate)
                del candidate[field]
                self.assert_rejected_before_routing(candidate)
        self.assert_rejected_before_routing(dict(self.candidate, approved=True))
        self.assert_rejected_before_routing(self.reply("invalid.json", self.message))
        for candidate in (None, [], "object", 42, True):
            with self.subTest(root=candidate):
                self.assert_rejected_before_routing(candidate)

    def test_T03_scalar_types_and_enums_are_strict(self):
        for field in SCALARS:
            for invalid in (False, 7, 1.5, [], {}):
                with self.subTest(field=field, invalid=invalid):
                    candidate = deepcopy(self.candidate)
                    candidate[field] = invalid
                    self.assert_rejected_before_routing(candidate)
        for field, allowed in (
            ("kind", ("new", "change", "withdrawal", "other", None)),
            ("environment", ("staging", "production", None)),
            ("permission", ("read", "write", "admin", None)),
        ):
            for value in allowed:
                with self.subTest(field=field, allowed=value):
                    candidate = deepcopy(self.candidate)
                    candidate[field] = value
                    self.validate(candidate, self.message)
            for invalid in ("unknown", "READ", ""):
                with self.subTest(field=field, invalid=invalid):
                    candidate = deepcopy(self.candidate)
                    candidate[field] = invalid
                    self.assert_rejected_before_routing(candidate)

    def test_T03_quote_and_issue_arrays_only_contain_strings(self):
        for field in ("supporting_quotes", "issues"):
            for invalid in (None, "text", {}, [None], [3], [False], [[]], [{}]):
                with self.subTest(field=field, invalid=invalid):
                    candidate = deepcopy(self.candidate)
                    candidate[field] = invalid
                    self.assert_rejected_before_routing(candidate)

    def test_T03_evidence_is_exact_decoded_message_substring(self):
        for quote in ("Production admin request", "2030-01-01T00:00:00Z",
                      "Maya Chen from Finance", "maya chen", "Maya  Chen"):
            with self.subTest(quote=quote):
                candidate = deepcopy(self.candidate)
                candidate["supporting_quotes"] = [quote]
                self.assert_rejected_before_routing(candidate)
        message = 'Maya said "read" access.\nUse Atlas.'
        candidate = deepcopy(self.candidate)
        candidate["supporting_quotes"] = ['"read" access.\nUse Atlas.']
        self.validate(candidate, message)
