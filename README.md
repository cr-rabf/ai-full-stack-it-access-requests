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
.venv/bin/access-requests --mock-config tests/mock_responses/corpus-config.json intake materials/requests --workers 4
.venv/bin/access-requests queue
.venv/bin/access-requests pending
.venv/bin/access-requests history --document IT-002.json
.venv/bin/access-requests --mock-config tests/mock_responses/corpus-config.json resume
.venv/bin/access-requests --mock-config tests/mock_responses/corpus-config.json retry --document IT-002.json
.venv/bin/access-requests export deliverables
```

Every command also works as `python3 -m access_requests` from the repository root.
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
python3 -m access_requests --model claude-sonnet-5-5 intake materials/requests --workers 4 --attempts 3 --backoff 1 --max-backoff 30
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

Accuracy evaluation and its exact command will be added in Step 9 using the approved
D5 rules, frozen before measurement. Mock extraction verifies plumbing and policy;
it does not measure real model generalization.
