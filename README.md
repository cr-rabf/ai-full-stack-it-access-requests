# IT access request intake

Prepare source messages for human review using an extraction model and the supplied
office policy. Approval belongs to human reviewers. The application supports CPython
3.10+ on Linux, one shared host and local disk. It uses only standard-library modules;
`requirements.lock` records that there are no third-party runtime dependencies.

Install offline, from the repository root:

```bash
python3 -m venv --without-pip .venv
.venv/bin/python tools/install.py --prefix .venv
```

Process the 20 supplied messages with saved mocks, inspect progress and history,
resume unfinished work, retry one document, and export a consistent snapshot:

```bash
.venv/bin/access_request --mock-config tests/mock_responses/corpus-config.json intake materials/requests --workers 4
.venv/bin/access_request queue
.venv/bin/access_request pending
.venv/bin/access_request history --document IT-002.json
.venv/bin/access_request --mock-config tests/mock_responses/corpus-config.json resume
.venv/bin/access_request --mock-config tests/mock_responses/corpus-config.json retry --document IT-002.json
.venv/bin/access_request export deliverables
```

Every command also works as `python3 -m access_request` from the repository root.
After installation, `.venv/bin/python -m access_request` also works from other
directories. The implementation remains in `src/`; `access_request.py` is the public
entry point. Re-run the installation command to update an existing installation.
Use the same `--db PATH` before each command to select another shared database;
the default is `.access-requests/state.sqlite3`. Inspect commands can run in a second
terminal during intake. Failed extraction returns exit code 1, command errors 2,
and successful work 0. Successful requests remain a queue awaiting human review.

The supported provider contract is Anthropic Messages API version `2026-10-21`,
model `claude-sonnet-5-5`. Set `API_KEY` in your shell for provider intake and omit
`--mock-config`. No other environment variable is required. Configure `--model`,
`--endpoint`, `--max-tokens`, or `--timeout` before the subcommand. Credentials are
loaded only on actual provider calls and redacted from request evidence; tests and
mock commands require no credentials. No live-provider accuracy claim is made.
See [provider contract](docs/provider-contract.md) for verified documentation links,
request settings, prompt/schema paths and response handling.

```bash
python3 -m access_request --model claude-sonnet-5-5 intake materials/requests --workers 4 --attempts 3 --backoff 1 --max-backoff 30
env -u API_KEY python3 -m unittest discover -s tests
```

The tests block networking, inject saved mock responses under `tests/mock_responses/`,
and derive expected facts from the source ledger rather than model runs. The clean
installation test exercises 400-message and 2,000-message authored workloads and
prints measured mock timings. Ordinary volume is assumed to be 200–400 messages/day,
with peaks around 2,000. These are workload assumptions, not provider throughput
guarantees. Host storage, credentials, provider capacity and rate limits affect actual
operation. See [operations and recovery](docs/operations.md) and the accepted
[implementation decisions](planning/decisions.md).

Export resolves one immutable generation for `extractions.jsonl`, `queue.json` and
`history.jsonl`, publishing it via `deliverables/current`. Resolve `current` once when
comparing files. Root links are convenient views; generation IDs expose mixed reads.
History preserves earlier versions and failures separately. Unchanged input/settings
reuse completed errors as well as successes; explicit retry always creates an attempt.

Evaluate the 20 supplied messages and the authored paraphrase with the frozen,
user-approved D5 rules. Reinstall after source changes to refresh the packaged CLI.

```bash
python3 -m access_request --mock-config tests/mock_responses/evaluation-config.json intake materials/paraphrases
python3 -m access_request export deliverables
env -u API_KEY python3 -m access_request accuracy --records deliverables/extractions.jsonl --report deliverables/accuracy.md
```

The denominator is 252 (12 scalars × 21 messages). Exact strings and explicit nulls
are compared without normalization. Failed/invalid records score zero of 12;
missing fields/documents count as incorrect. Routing and evidence are checked
separately. Expected fields and rules were committed before scorer implementation.
Mock extraction verifies plumbing and policy; it does not measure real model
generalization. Full details are in [accuracy.md](deliverables/accuracy.md).

Verify the committed handover artifacts, or repeat the isolated installed walkthrough:

```bash
env -u API_KEY python3 -m src.verification
env -u API_KEY python3 tools/walkthrough.py
```

See [verification.md](deliverables/verification.md) for observed results, operating
limits and pending facilitator capture/submission checks, and
[planning/test-run.txt](planning/test-run.txt) for the saved full-suite run.
