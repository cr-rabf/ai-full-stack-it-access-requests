"""Operator commands: durable progress, bounded scheduling and explicit recovery."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
from pathlib import Path
import shlex
import sys
import time

from .exports import read_export
from .mock_provider import MockProvider
from .provider import AnthropicProvider, ProviderConfig
from .review import intake
from .storage import Store, processing_settings


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def parser():
    result = argparse.ArgumentParser(prog="access_request", description="Prepare IT access requests for human review")
    result.add_argument("--db", default=".access-requests/state.sqlite3")
    result.add_argument("--mock-config", type=Path)
    result.add_argument("--model", default="claude-sonnet-5-5")
    result.add_argument("--endpoint", default="https://api.anthropic.com/v1/messages")
    result.add_argument("--max-tokens", type=positive, default=8192)
    result.add_argument("--timeout", type=float, default=60)
    result.add_argument("--prompt", type=Path)
    result.add_argument("--schema", type=Path)
    result.add_argument("--policy", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("intake", "resume", "retry"):
        command = commands.add_parser(name)
        if name == "intake":
            command.add_argument("source", type=Path)
        if name == "retry":
            command.add_argument("--document", required=True)
            command.add_argument("--source", type=Path)
        command.add_argument("--workers", type=positive, default=4)
        command.add_argument("--attempts", type=positive, default=1)
        command.add_argument("--backoff", type=float, default=1)
        command.add_argument("--max-backoff", type=float, default=30)
    commands.add_parser("queue")
    commands.add_parser("pending")
    history = commands.add_parser("history")
    history.add_argument("--document")
    export = commands.add_parser("export")
    export.add_argument("destination", type=Path)
    accuracy = commands.add_parser("accuracy")
    accuracy.add_argument("--records", type=Path, default=Path("deliverables/extractions.jsonl"))
    accuracy.add_argument("--expected", type=Path, default=Path("deliverables/expected-fields.json"))
    accuracy.add_argument("--rules", type=Path, default=Path("deliverables/accuracy-rules.json"))
    accuracy.add_argument("--sources", type=Path, default=Path("materials/requests"))
    accuracy.add_argument("--paraphrase", type=Path, default=Path("materials/paraphrases/IT-021.json"))
    accuracy.add_argument("--report", type=Path)
    return result


def make_provider(args):
    if args.mock_config:
        config = json.loads(args.mock_config.read_text(encoding="utf-8"))
        directory = args.mock_config.parent / config.get("fixtures_dir", ".")
        provider = MockProvider(directory, replies=config.get("replies"), scripts=config.get("scripts"))
        # Controls (delay/error sequences) are simulated transport behavior, not
        # request configuration. The saved configuration is retained for audit.
        provider.mock_config_path = str(args.mock_config.resolve())
    else:
        provider = AnthropicProvider(ProviderConfig(endpoint=args.endpoint, model=args.model,
                                     max_tokens=args.max_tokens, timeout=args.timeout),
                                     prompt_path=args.prompt, schema_path=args.schema, policy_path=args.policy)
    for attribute, path in (("prompt_path", args.prompt), ("schema_path", args.schema), ("policy_path", args.policy)):
        if path:
            setattr(provider, attribute, path)
    return provider


def execute_attempt(store, attempt, provider, args):
    try:
        for index in range(args.attempts):
            result, = intake([attempt.document], provider)
            if result["error"]:
                arguments = ["--db", str(Path(args.db).resolve())]
                if args.mock_config:
                    arguments.extend(["--mock-config", str(args.mock_config.resolve())])
                else:
                    arguments.extend(["--model", args.model, "--endpoint", args.endpoint,
                                      "--max-tokens", str(args.max_tokens), "--timeout", str(args.timeout)])
                for flag in ("prompt", "schema", "policy"):
                    path = getattr(args, flag)
                    if path:
                        arguments.extend([f"--{flag}", str(path.resolve())])
                arguments.extend(["retry", "--document", attempt.document.document_id])
                result["retry_arguments"] = arguments
                result["error"] = result["error"].split(". Retry:", 1)[0] + ". Retry: access_request " + shlex.join(arguments)
            result = store.complete(attempt, result)
            if (result.get("error_kind") not in ("timeout", "unavailable", "rate_limit")
                    or index + 1 == args.attempts):
                return result
            current = next(r for r in store.current() if r["document_id"] == result["document_id"])
            if current["attempt_id"] != result["attempt_id"]:
                return result
            delay = min(args.max_backoff, max(args.backoff * (2 ** index), result.get("retry_after_seconds", 0)))
            time.sleep(max(0, delay))
            attempt = store.begin(attempt.document, processing_settings(provider), retry=True)
        return result
    finally:
        attempt.close()


def schedule(store, attempts, provider, args):
    """Bound submitted futures to worker count; provider waits hold no DB lock."""
    results = [attempt.record for attempt in attempts if attempt.reused]
    iterator = iter(attempt for attempt in attempts if not attempt.reused)
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            active = set()
            for _ in range(args.workers):
                attempt = next(iterator, None)
                if attempt is not None:
                    active.add(pool.submit(execute_attempt, store, attempt, provider, args))
            while active:
                done, active = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    results.append(future.result())
                    attempt = next(iterator, None)
                    if attempt is not None:
                        active.add(pool.submit(execute_attempt, store, attempt, provider, args))
    finally:
        for attempt in attempts:
            attempt.close()
    return sorted(results, key=lambda record: (record["document_id"], record["attempt_id"]))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "accuracy":
            from .accuracy import score_records, write_report
            records = [json.loads(line) for line in args.records.read_text().splitlines() if line.strip()]
            expected = json.loads(args.expected.read_text())["records"]
            rules = json.loads(args.rules.read_text())
            paths = sorted(args.sources.glob("*.json")) + [args.paraphrase]
            documents = {path.name: read_export(path) for path in paths}
            output = score_records(records, expected, documents, rules)
            if args.report:
                write_report(args.report, output, expected, args.expected, args.rules)
            print(json.dumps(output, indent=2))
            return int(bool(output["factual_errors"] or output["unexpected_documents"]
                            or output["routing_errors"] or output["evidence_errors"]))
        store = Store(args.db)
        if args.command == "queue":
            output = store.current()
        elif args.command == "history":
            output = store.history(args.document)
        elif args.command == "pending":
            output = store.pending()
        elif args.command == "export":
            output = {"generation": str(store.export(args.destination))}
        else:
            if args.timeout <= 0 or args.backoff < 0 or args.max_backoff < 0:
                raise ValueError("Timeout must be positive; backoff values must be nonnegative")
            provider = make_provider(args)
            settings = processing_settings(provider)
            attempts = []
            if args.command == "intake":
                paths = [args.source] if args.source.is_file() else sorted(args.source.glob("*.json"))
                if not paths:
                    raise ValueError("No JSON source exports found")
                # Validate input before acquiring any durable attempt ownership.
                documents = [read_export(path) for path in paths]
                attempts = [store.begin(document, settings) for document in documents]
            elif args.command == "retry":
                if args.source:
                    document = read_export(args.source)
                    if document.document_id != args.document:
                        raise ValueError("Retry source filename must match --document")
                else:
                    with store.connection() as db:
                        row = db.execute("SELECT raw FROM attempts WHERE document_id=? ORDER BY id DESC LIMIT 1",
                                         (args.document,)).fetchone()
                    if row is None:
                        raise ValueError("Document is unknown; provide --source")
                    raw = row["raw"]
                    from .exports import SourceDocument
                    import hashlib
                    export = json.loads(raw.decode("utf-8"))
                    document = SourceDocument(args.document, raw, hashlib.sha256(raw).hexdigest(), export["message"],
                                              {k: v for k, v in export.items() if k != "message"})
                attempts = [store.begin(document, settings, retry=True)]
            else:
                for record in store.pending():
                    attempt = store.claim(record["attempt_id"])
                    if attempt is None:
                        continue
                    if attempt.settings != settings:
                        attempt.close()
                        raise ValueError("Pending settings differ; resume with original settings or explicitly retry the document")
                    attempts.append(attempt)
            output = schedule(store, attempts, provider, args)
        print(json.dumps(output, indent=2))
        return int(isinstance(output, list) and any(row.get("status") == "error" for row in output)
                   and args.command in ("intake", "resume", "retry"))
    except (ValueError, OSError, KeyError) as exc:
        print(f"access_request: {exc}", file=sys.stderr)
        return 2
