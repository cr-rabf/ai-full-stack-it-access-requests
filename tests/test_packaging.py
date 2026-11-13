"""T25: clean stdlib-only installation, corpus, retry/export, and authored loads."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import test_cli_operations


ROOT = Path(__file__).resolve().parents[1]
MOCKS = ROOT / "tests/mock_responses"
EXPECTED = json.loads((ROOT / "tests/expectations/source_facts.json").read_text())


class PackagingContract(unittest.TestCase):
    setUp = test_cli_operations.OperationsContract.setUp
    tearDown = test_cli_operations.OperationsContract.tearDown
    setUpGuards = test_cli_operations.OperationsContract.setUpGuards
    source = test_cli_operations.OperationsContract.source

    def test_T25_clean_install_corpus_retry_export_and_loads(self):
        prefix = self.directory / "venv"
        self.assertTrue((ROOT / "tools/install.py").is_file(), "CLI installer is missing")
        self.assertTrue((ROOT / "requirements.lock").is_file(), "Dependency lockfile is missing")
        self.assertTrue((ROOT / "access_request.py").is_file(), "access_request entry point is missing")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(prefix)], check=True,
                       env={}, capture_output=True, timeout=20)
        python = prefix / "bin/python"
        installed = subprocess.run([str(python), str(ROOT / "tools/install.py"), "--prefix", str(prefix)],
                                   env={}, capture_output=True, text=True, timeout=20)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        launcher = prefix / "bin/access-requests"
        def cli(*args, config=MOCKS / "corpus-config.json", db=None, code=0):
            command = [str(python), str(ROOT / "tests/cli_runner.py"), "--installed", str(launcher),
                       "--db", str(db or self.directory / "packaged.sqlite3"),
                       "--mock-config", str(config), *map(str, args)]
            run = subprocess.run(command, cwd=self.directory, env={}, capture_output=True,
                                 text=True, timeout=90)
            self.assertEqual(run.returncode, code, run.stderr + run.stdout)
            return json.loads(run.stdout)
        records = cli("intake", ROOT / "materials/requests")
        self.assertEqual(len(records), 20)
        routes = {
            "Owner": ("review", "System Owner", "review-request"),
            "Security": ("review", "Security Review", "review-risk-then-owner"),
            "Desk clarify": ("needs-information", "IT Service Desk", "clarify"),
            "Inspect": ("review", "IT Service Desk", "inspect-message"),
            "Withdraw": ("review", "IT Service Desk", "confirm-withdrawal"),
        }
        for record in records:
            expected = EXPECTED[record["document_id"]]
            for field, value in expected["facts"].items():
                self.assertEqual(record["extraction"][field], value)
            self.assertEqual(tuple(record[field] for field in ("status", "owner", "next_action")),
                             routes[expected["route"]])
            self.assertEqual(record["response_source"], "mock")
            self.assertIsNone(record["error"])
            raw = (ROOT / "materials/requests" / record["document_id"]).read_bytes()
            self.assertEqual(record["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(cli("queue")), 20)
        # Use the installed module from outside the repository, with cwd and
        # PYTHONPATH excluded from Python's import search. Guards still prohibit
        # network connections and API_KEY reads in the child process.
        module = subprocess.run([
            str(python), "-I", str(ROOT / "tests/cli_runner.py"), "--installed-module",
            "--db", str(self.directory / "packaged.sqlite3"), "queue",
        ], cwd=self.directory, env={}, capture_output=True, text=True, timeout=15)
        self.assertEqual(module.returncode, 0, module.stderr)
        self.assertEqual(len(json.loads(module.stdout)), 20)
        named_launcher = prefix / "bin/access_request"
        named = subprocess.run([
            str(python), str(ROOT / "tests/cli_runner.py"), "--installed", str(named_launcher),
            "--db", str(self.directory / "packaged.sqlite3"), "queue",
        ], cwd=self.directory, env={}, capture_output=True, text=True, timeout=15)
        self.assertEqual(named.returncode, 0, named.stderr)
        self.assertEqual(json.loads(named.stdout), json.loads(module.stdout))
        self.assertEqual(cli("pending"), [])
        rerun = cli("intake", ROOT / "materials/requests")
        self.assertEqual([r["attempt_id"] for r in records], [r["attempt_id"] for r in rerun])
        failed = cli("retry", "--document", "IT-002.json", config=MOCKS / "cli-outage.json", code=1)
        self.assertEqual(failed[0]["status"], "error")
        fixed = cli("retry", "--document", "IT-002.json")
        self.assertEqual(fixed[0]["owner"], "Security Review")
        self.assertEqual(len(cli("history", "--document", "IT-002.json")), 3)
        output = cli("export", self.directory / "outputs")
        generation = Path(output["generation"])
        queue = json.loads((generation / "queue.json").read_text())
        extractions = [json.loads(line) for line in (generation / "extractions.jsonl").read_text().splitlines()]
        self.assertEqual(len(queue), 20)
        self.assertEqual({(r["document_id"], r["attempt_id"], r["source_sha256"]) for r in queue},
                         {(r["document_id"], r["attempt_id"], r["source_sha256"]) for r in extractions})
        template = json.loads((ROOT / "tests/fixtures/paraphrase-021-export.json").read_text())
        for count in (400, 2000):
            source = self.directory / f"load-{count}"
            source.mkdir()
            replies = {}
            for number in range(1, count + 1):
                identifier = f"LOAD-{number:04d}"
                export = dict(template, message=template["message"].replace("IT-021", identifier))
                (source / f"{identifier}.json").write_text(json.dumps(export), encoding="utf-8")
                replies[f"{identifier}.json"] = {"reply": "load-owner.json", "request_id": identifier}
            config = self.directory / f"load-{count}-config.json"
            config.write_text(json.dumps({"fixtures_dir": str(MOCKS), "replies": replies}))
            started = time.monotonic()
            records = cli("intake", source, "--workers", "4", config=config,
                          db=self.directory / f"load-{count}.sqlite3")
            elapsed = time.monotonic() - started
            self.assertEqual(len(records), count)
            self.assertEqual(len({r["document_id"] for r in records}), count)
            for record in records:
                identifier = Path(record["document_id"]).stem
                self.assertEqual(record["extraction"]["request_id"], identifier)
                self.assertEqual(record["extraction"]["manager"], "Priya Shah")
                self.assertEqual(record["owner"], "System Owner")
                self.assertEqual(record["extraction"]["issues"], [])
                self.assertEqual(record["response_source"], "mock")
                self.assertIsNone(record["error"])
            print(f"T25 observed: {count} saved-mock messages, workers=4, {elapsed:.3f}s; not provider throughput.")
