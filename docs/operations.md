# Local shared operation

Use one Linux host and one local-disk database shared by operators. SQLite WAL
transactions order attempt starts; newest start is current even while pending.
Pending work is durable before the provider call. Completion updates one attempt
atomically. Older completions remain in history. Model waits hold only their own
attempt ownership lock, not a database or publication lock.

Inspect while intake is running:

```
python3 -m access_request --db .access-requests/state.sqlite3 queue
python3 -m access_request --db .access-requests/state.sqlite3 pending
python3 -m access_request --db .access-requests/state.sqlite3 history --document IT-002.json
```

Resume uses saved source bytes and original settings. It skips attempts whose OS
locks are held, including attempts owned by another operator. Process death releases
the locks; an orphan remains pending until explicitly resumed. A resume with changed
settings is rejected; explicitly retry to create an attempt with new settings.

```
python3 -m access_request --mock-config tests/mock_responses/cli-delayed.json resume
python3 -m access_request --mock-config tests/mock_responses/cli-immediate.json retry --document IT-002.json
```

`intake`, `resume`, and `retry` accept `--workers`, `--attempts`, `--backoff`, and
`--max-backoff`. Attempts default to one; automatic retries apply only to service
timeouts, unavailability and rate limits. Backoff is exponential, respects numeric
Retry-After and is bounded by max-backoff. Each failed attempt remains in history.
The scheduler submits at most workers futures; no DB lock spans provider waits.
Unchanged errors are reused until explicit retry or relevant input/settings change.
CLI failures include `retry_arguments` preserving the database, mock configuration
or model/request settings, and custom prompt/schema/policy paths. Pass those
arguments to the same CLI installation; the human-readable error also shows them.

`export DESTINATION` writes an immutable generation, flushes it, and atomically
switches the destination's `current` symlink. Resolve that symlink once before
reading queue and extraction files together. An interrupted unpublished generation
is ignored; export again to publish a complete snapshot. Root file links point into
current for convenience, and generation IDs detect cross-generation comparisons.
History is a separate JSONL file. Retain generation directories while readers use them.

Tests cover two concurrent operators, out-of-order completions, delayed inspection,
process termination/resume and an injected interruption before snapshot publication.
They establish local operational behavior with saved mock responses, not live
provider throughput. Network filesystems, cross-host locking, disk loss, power loss,
and provider billing deduplication after a crash are outside this verification.
