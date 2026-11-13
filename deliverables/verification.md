# Verification and submission handover

Intended comparisons are distinct from Observed results below. All implementation
checks use saved mock responses; no live-provider observation is claimed.

Intended checks and reproducible commands:

```bash
env -u API_KEY python3 -m unittest discover -s tests -v
env -u API_KEY python3 tools/walkthrough.py --output deliverables/c1-results.json
env -u API_KEY python3 -m access_requests accuracy --records deliverables/extractions.jsonl
env -u API_KEY python3 -m access_requests.verification
git diff --check
```

T01 verifies saved fixture selection/call accounting without network/key access.
T02–T03 compare original-byte hashes, export identity, exact decoded quotes and
the supplied schema, including the 200-word boundary. T04–T07 compare the implemented
HTTP request and handling against a fake transport: exceptions, refusal, cutoff,
malformed JSON, invalid schema and invalid evidence never reach routing.
T08–T15 compare source-ledger facts and ordered human-review routes. T16 rejects
incomplete or invented expectations for independently authored wording.
T17–T21 compare reuse, changed-source hashes, current attempts and retained history,
including failed retries and both completion orders. T22–T24 inspect while work is
delayed, bound service retries, detect settings refresh and verify interruption
recovery by process termination plus an injected snapshot-publication failure.
T25 installs offline and processes the full corpus plus 400/2,000 authored mock
messages. T26 checks the frozen D5 denominator and known wrong/null/missing/failed
output counts. T27 compares current artifacts, schema, hashes, history links,
redacted request evidence, provenance and repeatable mocked results.

Observed final verification: all 44 tests passed in 32.662 seconds on Python 3.12.3/Linux.
The full command output is saved in `planning/test-run.txt`. The T25
run used the saved `load-owner.json` template, replacing only authored request IDs,
with four workers: 400 messages took 4.121 seconds; 2,000 took 20.239 seconds.
These measurements are local mock timings, not provider throughput estimates.
The committed 21-record mock snapshot scored 252/252 scalar matches, with no
factual, routing or evidence differences. Expectations/rules were frozen in
commit `ffa3171` before scorer implementation, independently of measured outputs.

C1: passed the isolated installed setup/intake/queue/history/pending/resume/retry/export/accuracy
walkthrough on Python 3.12.3/Linux, using saved mocks. All ten CLI commands exited 0;
21 documents were processed and scored 252/252. Exact command arguments and observed
results are recorded in [c1-results.json](c1-results.json). Review `requirements.lock`,
the extraction prompt, schema, [provider contract](../docs/provider-contract.md),
[accuracy report](accuracy.md), and accepted [D1–D5 decisions](../planning/decisions.md).
Full-suite results are saved in [test-run.txt](../planning/test-run.txt).
The artifact verifier also passed for all 21 documents with 252 scalar matches,
only mock response sources and no consistency/provenance/redaction errors.

C2: pending facilitator capture instructions and inspection of the actual session
record paired with the submitted commit. Repository context says Entire is enabled;
ordinary commits capture automatic checkpoints. This does not prove facilitator
capture pairing, and no manual checkpoint was created.

C3: pending the real push and Classroom submission workflow. No push, Classroom
submission or facilitator capture pairing is claimed by this implementation.
At submission, verify the default-branch commit contains application, outputs and
the required capture; submit only the repository root link.

Operating assumptions and limits: one Linux host, shared local-disk SQLite, OS
attempt locks, 200–400 messages/day and peaks around 2,000. Each pending attempt is
saved before the provider call. Completion is atomic and the newest-started attempt
remains current. Process death releases locks; `resume` claims unfinished work
using saved bytes and matching settings. A provider call may be repeated after a
crash before completion, so provider billing deduplication is not guaranteed.
Unchanged errors are reused; explicit retry creates an attempt. Queue/extraction
readers must pin `current` once to compare an immutable export generation.
Partial unpublished generations are ignored and a later export repairs publication.
Tests verify process interruption and a controlled publication fault, not power
loss, disk loss, network filesystems, cross-host operation, arbitrary provider
capacity or real model generalization. The declared supported runtime is 3.10+;
recorded execution uses the runtime identified in C1 results and test evidence.

Observed repairs: implementation addressed the missing modules/capabilities shown
by each Test first commit. Handover review found that retry guidance omitted custom
database/provider settings; a failing copy-and-execute regression check preceded
the fix. Errors now retain executable retry arguments for the original state and
provider configuration. No live-provider factual-error repair is claimed.
