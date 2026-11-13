"""T17–T21: accepted D1–D4, saved replies, durable coherent current/history views."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import test_review_policy


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"


class StorageContract(unittest.TestCase):
    setUpGuards = test_review_policy.ReviewPolicyContract.setUp
    tearDown = test_review_policy.ReviewPolicyContract.tearDown
    source = test_review_policy.ReviewPolicyContract.source

    def setUp(self):
        self.setUpGuards()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        from access_requests.storage import Store, processing_settings
        self.store_class = Store
        self.settings = processing_settings
        self.store = Store(self.directory / "state.sqlite3")
        self.provider = self.provider_class(MOCKS, replies={
            "IT-001.json": "complete-001.json", "IT-002.json": "complete-002.json"})

    def updated_source(self):
        original = self.source(1)
        source = json.loads(original.raw_bytes)
        source["message"] += " Correction: environment is production. All other request details remain the same."
        path = self.directory / "IT-001.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        return self.read_export(path)

    def test_T17_unchanged_success_and_error_reuse(self):
        first = self.store.process(self.source(1), self.provider)
        second = self.store.process(self.source(1), self.provider)
        self.assertEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(len(self.store.current()), 1)
        self.assertEqual(len(self.store.history("IT-001.json")), 1)
        failure = self.provider_class(MOCKS, scripts=json.loads((MOCKS / "persistence-failure.json").read_text()))
        failed = self.store.process(self.source(1), failure, retry=True)
        reused = self.store.process(self.source(1), failure)
        self.assertEqual(failed["status"], "error")
        self.assertEqual(failed["attempt_id"], reused["attempt_id"])
        self.assertEqual(len(failure.calls), 1)

    def test_T18_changed_bytes_retain_previous_hash_and_publish_matching_generation(self):
        first = self.store.process(self.source(1), self.provider)
        provider = self.provider_class(MOCKS, replies={"IT-001.json": "updated-001.json"})
        updated = self.updated_source()
        second = self.store.process(updated, provider)
        self.assertNotEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(first["owner"], "System Owner")
        self.assertEqual(second["owner"], "Security Review")
        self.assertEqual([r["source_sha256"] for r in self.store.history("IT-001.json")],
                         [first["source_sha256"], second["source_sha256"]])
        self.assertEqual(self.store.current()[0]["attempt_id"], second["attempt_id"])
        generation = self.store.export(self.directory / "outputs")
        queue = json.loads((generation / "queue.json").read_text())
        extraction = json.loads((generation / "extractions.jsonl").read_text())
        for field in ("document_id", "attempt_id", "source_sha256", "generation_id"):
            self.assertEqual(queue[0][field], extraction[field])
        self.assertEqual(extraction["extraction"]["environment"], "production")
        self.assertTrue((generation / "history.jsonl").is_file())

    def test_T19_failed_retry_is_current_and_prior_success_survives(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                store = self.store_class(self.directory / f"retry-{changed}.sqlite3")
                first = store.process(self.source(1), self.provider)
                source = self.updated_source() if changed else self.source(1)
                failure = self.provider_class(MOCKS, scripts=json.loads((MOCKS / "persistence-failure.json").read_text()))
                failed = store.process(source, failure, retry=True)
                self.assertEqual(failed["status"], "error")
                self.assertIsNone(failed["extraction"])
                self.assertIn("IT-001.json", failed["error"])
                self.assertEqual(store.current()[0]["attempt_id"], failed["attempt_id"])
                history = store.history("IT-001.json")
                self.assertEqual(history[0]["attempt_id"], first["attempt_id"])
                self.assertEqual(history[0]["owner"], "System Owner")
                self.assertEqual(history[0]["source_sha256"], first["source_sha256"])
                self.assertEqual(len(history), 2)

    def test_T20_newest_started_wins_in_both_completion_orders(self):
        for newer_first in (False, True):
            with self.subTest(newer_first=newer_first):
                store = self.store_class(self.directory / f"overlap-{newer_first}.sqlite3")
                old = store.begin(self.source(1), self.settings(self.provider))
                new = store.begin(self.updated_source(), self.settings(self.provider))
                self.assertEqual(store.current()[0]["attempt_id"], new.attempt_id)
                self.assertEqual(store.current()[0]["status"], "pending")
                older_result = self.intake([self.source(1)], self.provider)[0]
                updated_provider = self.provider_class(MOCKS, replies={"IT-001.json": "updated-001.json"})
                newer_result = self.intake([self.updated_source()], updated_provider)[0]
                pairs = [(new, newer_result), (old, older_result)] if newer_first else [(old, older_result), (new, newer_result)]
                for attempt, result in pairs:
                    store.complete(attempt, result)
                    self.assertEqual(store.current()[0]["attempt_id"], new.attempt_id)
                self.assertEqual(store.current()[0]["extraction"]["environment"], "production")
                self.assertEqual(len(store.history("IT-001.json")), 2)
        # Concurrent unchanged starts share one pending attempt and perform one call.
        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = list(pool.map(lambda _: self.store.begin(self.source(1), self.settings(self.provider)), range(2)))
        self.assertEqual(attempts[0].attempt_id, attempts[1].attempt_id)
        self.assertEqual(sum(not a.reused for a in attempts), 1)
        for attempt in attempts:
            attempt.close()

    def test_T21_later_batch_omission_keeps_earlier_document(self):
        first = self.store.process(self.source(1), self.provider)
        self.store.process(self.source(2), self.provider)
        self.store.process(self.source(2), self.provider)
        current = {r["document_id"]: r for r in self.store.current()}
        self.assertEqual(set(current), {"IT-001.json", "IT-002.json"})
        self.assertEqual(current["IT-001.json"]["attempt_id"], first["attempt_id"])
        self.assertEqual(current["IT-001.json"]["owner"], "System Owner")
        self.assertEqual(current["IT-002.json"]["owner"], "Security Review")
