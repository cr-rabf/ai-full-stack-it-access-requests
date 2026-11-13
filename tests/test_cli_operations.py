"""T22–T24: independent CLI inspection, retry bounds, refresh and crash recovery."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import test_storage


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"


class OperationsContract(unittest.TestCase):
    setUp = test_storage.StorageContract.setUp
    tearDown = test_storage.StorageContract.tearDown
    setUpGuards = test_storage.StorageContract.setUpGuards
    source = test_storage.StorageContract.source

    def command(self, *arguments, config="cli-immediate.json"):
        return [sys.executable, str(ROOT / "tests/cli_runner.py"),
                "--db", str(self.directory / "state.sqlite3"),
                "--mock-config", str(MOCKS / config), *arguments]

    def cli(self, *arguments, config="cli-immediate.json", expected_code=0):
        result = subprocess.run(self.command(*arguments, config=config), cwd=ROOT,
                                env={"PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected_code, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def exports(self):
        source = self.directory / "input"
        source.mkdir(exist_ok=True)
        for number in (1, 2):
            document = self.source(number)
            (source / document.document_id).write_bytes(document.raw_bytes)
        return source

    def wait_for_completed_and_pending(self, process):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            current = {r["document_id"]: r for r in self.store.current()}
            if (current.get("IT-001.json", {}).get("status") == "review"
                    and current.get("IT-002.json", {}).get("status") == "pending"):
                return current
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(f"Intake exited before independent inspection: {stdout} {stderr}")
            time.sleep(0.02)
        self.fail("Timed out waiting for completed and pending work")

    def test_T22_separate_cli_inspects_progress_while_another_request_waits(self):
        process = subprocess.Popen(self.command("intake", str(self.exports()), "--workers", "2",
                                               config="cli-delayed.json"), cwd=ROOT,
                                   env={"PYTHONPATH": str(ROOT)}, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            self.wait_for_completed_and_pending(process)
            queue = {r["document_id"]: r for r in self.cli("queue")}
            self.assertEqual(queue["IT-001.json"]["owner"], "System Owner")
            self.assertEqual(queue["IT-002.json"]["status"], "pending")
            pending = self.cli("pending")
            self.assertEqual([r["document_id"] for r in pending], ["IT-002.json"])
            self.assertEqual(self.cli("resume", config="cli-delayed.json"), [])
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr + stdout)
            self.assertEqual(self.cli("pending"), [])
            current = {r["document_id"]: r for r in self.cli("queue")}
            self.assertEqual(current["IT-002.json"]["owner"], "Security Review")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_T23_bounded_retry_outage_and_processing_identity(self):
        results = self.cli("intake", str(self.exports()), "--workers", "2", "--attempts", "3",
                           "--backoff", "0", config="cli-retry.json")
        self.assertEqual({r["status"] for r in results}, {"review"})
        history = self.cli("history", "--document", "IT-002.json")
        self.assertEqual([r.get("error_kind") for r in history], ["rate_limit", "timeout", None])
        self.assertEqual(len(self.cli("history", "--document", "IT-001.json")), 1)
        failed = self.cli("retry", "--document", "IT-002.json", "--attempts", "2", "--backoff", "0",
                          config="cli-outage.json", expected_code=1)
        self.assertEqual(failed[0]["status"], "error")
        self.assertIn("retry", failed[0]["error"])
        self.assertEqual(len(self.cli("history", "--document", "IT-002.json")), 5)
        self.assertEqual(self.cli("pending"), [])
        fixed = self.cli("retry", "--document", "IT-002.json")
        self.assertEqual(fixed[0]["owner"], "Security Review")
        # Relevant settings and content identities refresh; operation-only settings do not.
        document = self.source(1)
        baseline = self.store.process(document, self.provider)
        for attribute, source_path in (
            ("prompt_path", ROOT / "src/extraction_prompt.txt"),
            ("schema_path", ROOT / "snapshot.schema.json"),
            ("policy_path", ROOT / "materials/office-policy.md"),
        ):
            path = self.directory / attribute
            path.write_bytes(source_path.read_bytes() + b"\n")
            setattr(self.provider, attribute, path)
            refreshed = self.store.process(document, self.provider)
            self.assertNotEqual(refreshed["attempt_id"], baseline["attempt_id"])
            self.assertNotEqual(refreshed["processing_settings"], baseline["processing_settings"])
            baseline = refreshed
        self.provider.provenance = lambda: {"provider": "mock", "model": "changed-test-model"}
        refreshed = self.store.process(document, self.provider)
        self.assertNotEqual(refreshed["attempt_id"], baseline["attempt_id"])
        again = self.store.process(document, self.provider)
        self.assertEqual(again["attempt_id"], refreshed["attempt_id"])

    def test_T24_process_death_resume_and_atomic_publication_recovery(self):
        process = subprocess.Popen(self.command("intake", str(self.exports()), "--workers", "2",
                                               config="cli-delayed.json"), cwd=ROOT,
                                   env={"PYTHONPATH": str(ROOT)}, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            before = self.wait_for_completed_and_pending(process)
            process.kill()
            process.communicate(timeout=5)
            self.assertEqual(len(self.cli("pending")), 1)
            resumed = self.cli("resume", config="cli-delayed.json")
            self.assertEqual([r["document_id"] for r in resumed], ["IT-002.json"])
            self.assertEqual(resumed[0]["attempt_id"], before["IT-002.json"]["attempt_id"])
            self.assertEqual(resumed[0]["owner"], "Security Review")
            self.assertEqual(self.cli("pending"), [])
            history = self.cli("history", "--document", "IT-001.json")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["attempt_id"], before["IT-001.json"]["attempt_id"])
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
        output = self.directory / "outputs"
        published = self.store.export(output)
        def crash(stage):
            if stage == "after_extractions":
                raise RuntimeError("Injected publication interruption")
        with self.assertRaisesRegex(RuntimeError, "Injected"):
            self.store.export(output, fault=crash)
        self.assertEqual((output / "current").resolve(), published)
        recovered = self.store.export(output)
        self.assertEqual((output / "current").resolve(), recovered)
        queue = json.loads((recovered / "queue.json").read_text())
        records = [json.loads(line) for line in (recovered / "extractions.jsonl").read_text().splitlines()]
        self.assertEqual({r["generation_id"] for r in queue}, {r["generation_id"] for r in records})
        self.assertEqual({(r["document_id"], r["attempt_id"], r["source_sha256"]) for r in queue},
                         {(r["document_id"], r["attempt_id"], r["source_sha256"]) for r in records})
