"""C1: execute the documented offline workflow in an isolated installed environment."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workspace = Path(tempfile.mkdtemp(prefix="access-requests-c1-"))
    prefix = workspace / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(prefix)],
                   check=True, env={}, capture_output=True)
    python = prefix / "bin/python"
    subprocess.run([str(python), str(ROOT / "tools/install.py"), "--prefix", str(prefix)],
                   check=True, env={}, capture_output=True)
    observed = []
    def cli(*arguments):
        command = [str(python), str(ROOT / "tests/cli_runner.py"), "--installed", str(prefix / "bin/access-requests"),
                   "--db", str(workspace / "state.sqlite3"), "--mock-config",
                   str(ROOT / "tests/mock_responses/evaluation-config.json"), *map(str, arguments)]
        result = subprocess.run(command, cwd=workspace, env={}, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(f"Walkthrough command failed: {arguments}: {result.stderr}")
        value = json.loads(result.stdout)
        observed.append({"arguments": list(map(str, arguments)), "exit_code": result.returncode})
        return value
    corpus = cli("intake", ROOT / "materials/requests", "--workers", "4")
    assert len(corpus) == 20
    paraphrase = cli("intake", ROOT / "materials/paraphrases")
    assert len(paraphrase) == 1
    queue = cli("queue")
    assert len(queue) == 21
    assert cli("pending") == []
    assert cli("resume") == []
    before = cli("history", "--document", "IT-002.json")
    retried = cli("retry", "--document", "IT-002.json")
    assert retried[0]["owner"] == "Security Review"
    after = cli("history", "--document", "IT-002.json")
    assert len(before) == 1 and len(after) == 2
    exported = cli("export", workspace / "outputs")
    generation = Path(exported["generation"])
    assert len(json.loads((generation / "queue.json").read_text())) == 21
    scored = cli("accuracy", "--records", generation / "extractions.jsonl",
                 "--expected", ROOT / "deliverables/expected-fields.json",
                 "--rules", ROOT / "deliverables/accuracy-rules.json",
                 "--sources", ROOT / "materials/requests", "--paraphrase", ROOT / "materials/paraphrases/IT-021.json",
                 "--report", workspace / "accuracy.md")
    assert scored["matched"] == 252 and scored["total"] == 252
    result = {"check": "C1", "passed": True, "runtime": platform.python_version(),
              "platform": platform.system(), "response_source": "mock",
              "configuration": "tests/mock_responses/evaluation-config.json, workers=4, default request settings",
              "workspace": str(workspace), "documents": 21, "scalar_matches": 252,
              "commands": observed, "limits": "No live provider calls, cross-host tests or facilitator submission verification"}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
