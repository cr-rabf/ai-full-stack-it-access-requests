"""T01: application mock contract; facts are specified in planning/plan.md.

These checks exercise adapter behavior, not model accuracy or business routing.
All provider responses and scripted outcomes come from saved fixtures.
"""
import json
import os
from pathlib import Path
import socket
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests" / "mock_responses"


class NoCredentials(dict):
    def __getitem__(self, key):
        if key == "API_KEY":
            raise AssertionError("mock adapter attempted to read API_KEY")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "API_KEY":
            raise AssertionError("mock adapter attempted to read API_KEY")
        return super().get(key, default)


class MockProviderContract(unittest.TestCase):
    def setUp(self):
        # Guards include import time, construction, and every extraction call.
        self.network = mock.Mock(side_effect=AssertionError("network access forbidden"))
        for patcher in (
            mock.patch.object(socket, "socket", self.network),
            mock.patch.object(socket, "create_connection", self.network),
            mock.patch.object(os, "environ", NoCredentials()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        from src.mock_provider import MockProvider

        self.provider_class = MockProvider
        self.message = json.loads(
            (ROOT / "materials/requests/IT-001.json").read_text(encoding="utf-8")
        )["message"]
        self.scripts = json.loads(
            (MOCKS / "mock-contract-script.json").read_text(encoding="utf-8")
        )

    def tearDown(self):
        self.network.assert_not_called()

    def test_T01_named_reply_is_deterministic_and_tracks_calls(self):
        provider = self.provider_class(MOCKS, replies={"IT-001.json": "complete-001.json"})
        first = provider.extract("IT-001.json", self.message)
        second = provider.extract("IT-001.json", self.message)
        self.assertEqual(first, second)
        self.assertEqual(first["response_source"], "mock")
        self.assertEqual(first["status"], "completed")
        self.assertIsNone(first["refusal"])
        self.assertIsInstance(first["output_text"], str)
        self.assertTrue(first["output_text"])
        self.assertEqual(provider.calls, [
            {"document_id": "IT-001.json", "message": self.message},
            {"document_id": "IT-001.json", "message": self.message},
        ])
        # A caller cannot mutate the saved response seen by a later call.
        first["status"] = "corrupted"
        self.assertEqual(provider.extract("IT-001.json", self.message)["status"], "completed")

    def test_T01_saved_script_delays_errors_refuses_interrupts_and_recovers(self):
        sleep = mock.Mock()
        provider = self.provider_class(MOCKS, scripts=self.scripts, sleep=sleep)
        first = provider.extract("IT-001.json", self.message)
        sleep.assert_not_called()
        self.assertEqual(provider.extract("IT-001.json", self.message), first)
        sleep.assert_called_once_with(2)
        with self.assertRaisesRegex(RuntimeError, "Mock provider unavailable"):
            provider.extract("IT-001.json", self.message)
        refused = provider.extract("IT-001.json", self.message)
        self.assertEqual(refused["response_source"], "mock")
        self.assertEqual(refused["refusal"], "Mock provider declined extraction.")
        self.assertIsNone(refused["output_text"])
        with self.assertRaisesRegex(InterruptedError, "Mock request interrupted"):
            provider.extract("IT-001.json", self.message)
        self.assertEqual(provider.extract("IT-001.json", self.message), first)
        self.assertEqual(len(provider.calls), 6)
        self.assertTrue(all(call == {"document_id": "IT-001.json", "message": self.message}
                            for call in provider.calls))
        # Script exhaustion must not silently invent another successful reply.
        with self.assertRaisesRegex(RuntimeError, "exhausted"):
            provider.extract("IT-001.json", self.message)

    def test_T01_unknown_document_does_not_invent_a_reply(self):
        provider = self.provider_class(MOCKS, replies={"IT-001.json": "complete-001.json"})
        with self.assertRaisesRegex(KeyError, "IT-999.json"):
            provider.extract("IT-999.json", self.message)
