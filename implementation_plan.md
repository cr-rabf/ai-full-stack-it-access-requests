# IT Access Request Intake Application

## Current Task: 
 codex resume 01a1c141-82e6-71a0-993d-bfc5f6477dd1
 
## Summary

Build a Python CLI that extracts access requests with OpenAI, validates the results, and applies the supplied policy to produce a human review queue.

Use SQLite for durable state shared by concurrent operator processes on one host. Include reproducible mocked responses, an implemented live provider adapter, automated verification, and every deliverable required by `CHALLENGE.md`.

## Application and operator interface

- Use Python 3.12, `uv` with a committed lockfile, Typer, the OpenAI Python SDK, JSON Schema validation, and pytest.
- Provide these commands through `uv run access-intake`:

  | Command | Behavior |
  |---|---|
  | `intake materials/requests --provider mock` | Register new or changed exports and process available work |
  | `intake materials/requests --provider openai` | Run the same workflow using OpenAI |
  | `resume` | Continue durable pending work and recover expired worker leases |
  | `queue --watch` | Display completed results and pending/error counts during intake |
  | `show IT-016.json` | Display the current attempt, source evidence, issues, and provenance |
  | `history IT-016.json` | Inspect earlier source versions and processing attempts |
  | `retry IT-016.json` | Create a new attempt using the stored source and recorded configuration |
  | `refresh` | Reprocess stored documents whose processing fingerprint differs from current settings |
  | `export --output deliverables` | Generate consistent extraction and queue snapshots |
  | `accuracy --expected tests/fixtures/expected.json` | Compare current results with independently authored expectations |

- Support `--db`, queue filters, JSON output, and actionable nonzero exit codes for command failures. Intake reports individual errors while continuing other messages.
- Separate processing state—pending, running, retry-wait, completed, error—from policy status. Pending requests must not appear ready for review.
- Keep approval and access provisioning outside the application.

## Implementation

### Durable intake and shared operation

- Store immutable source bytes, filename, SHA-256, export metadata, processing configuration, attempts, errors, and validated results. Use the filename as `document_id`; never merge documents by their extracted request ID.
- Use SQLite WAL mode, short transactions, a busy timeout, transactional job claims, renewable leases, and claim tokens. Never hold a database transaction during a model call.
- Prevent duplicate scheduling for the same document, source hash, and processing fingerprint. Reuse unchanged successful results; leave failed work visible until retried.
- Include provider/model settings and hashes of the prompt, schema, policy, and routing version in the fingerprint. Exclude credentials.
- Define revision order by registration transaction order because the export format has no authoritative revision number. An older worker finishing late cannot replace a newer registered revision.
- Publish each completed attempt immediately. A failed newer attempt becomes the current error with null extraction; the earlier success remains available only as clearly identified history.
- Missing documents in subsequent batches remain active. Withdrawal is handled from message content.
- Generate both deliverable files from one database read snapshot. Serialize exports, publish through temporary files, and include a generation/checksum manifest so interrupted publication is detectable and recoverable by rerunning `export`.

### Extraction and provider handling

- Treat only the decoded `message` as the source of business facts. Hash original file bytes; validate malformed exports independently.
- Send messages as untrusted data with instructions covering nulls, conflicting alternatives, explicit corrections, relative dates, changed permissions, and exact evidence quotes.
- Use the OpenAI Responses API with strict structured output matching the supplied schema. Check completion and refusal before parsing, then validate locally. This follows the [official Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs).
- Default the supported live configuration to `gpt-4.1-mini-2025-04-14`, temperature `0`, maximum output tokens `2000`, and `store=false`. Keep the model configurable; document the supported configuration and any account-access limitations.
- Use `API_KEY` as required. Configure provider, model, database location, concurrency, request rate, timeout, and retry limits through documented `ACCESS_*` environment variables and CLI options.
- Default to four concurrent calls and a shared database-backed limit of 60 requests/minute. Use a 45-second request timeout, three total attempts for transient failures, exponential backoff with jitter, and provider retry hints. Disable overlapping SDK retries.
- Persist retry schedules so delays do not block other documents. Handle authentication failures, rate limits, network errors, malformed responses, refusals, and incomplete responses explicitly.
- Check calendar dates, quote substrings, required facts, identifier mismatch, and date ordering. Preserve explicit reversed dates and add a clarification issue.
- Detect instruction-override evidence conservatively in application checks as well as extraction. Preserve the attempted instruction; never execute message instructions.
- Provide mock responses through the same response-handling pipeline. Keep mock fixtures separate from accuracy expectations and reject unsupported mock inputs clearly.

### Policy routing

Implement the five policy rules in their exact order, with structured internal issue categories supporting deterministic routing:

1. Instruction override → IT Service Desk / `review` / `inspect-message`.
2. Withdrawal with request ID and request date → IT Service Desk / `review` / `confirm-withdrawal`.
3. Missing required facts, unresolved conflicts, identifier mismatch, invalid date order, or other/null kind → IT Service Desk / `needs-information` / `clarify`.
4. Complete production, write, or admin requests → Security Review / `review` / `review-risk-then-owner`.
5. Complete staging/read requests → System Owner / `review` / `review-request`.

Extraction failures produce IT Service Desk / `error` / `retry-extraction`, with an actionable error and null extraction.

Preserve the supplied extraction schema unchanged. Add provenance and operational metadata to the surrounding record: attempt ID, processing state, configuration fingerprint, policy version, and timestamps. Queue entries reference the same document, source hash, and attempt as their extraction records.

## Accuracy and verification

Author expected facts directly from all 20 messages and the policy before generating measured outputs. Add one independently written paraphrase with explicit expected facts.

Expected routing for the supplied dataset:

| Outcome | Documents |
|---|---|
| System Owner | IT-001, IT-008, IT-015, IT-018 |
| Security Review | IT-002, IT-007, IT-012, IT-013, IT-019 |
| Clarification | IT-003, IT-004, IT-009, IT-010, IT-011, IT-014, IT-016, IT-017, IT-020 |
| Inspect instruction override | IT-006 |
| Confirm withdrawal | IT-005 |

- Check all 12 scalar extraction fields for each of 21 messages: **252 comparisons**. Use exact equality, including nulls; any acceptable alternative wording must be authored in advance. Missing or failed records count as failed comparisons.
- Score status, owner, and next action separately: **63 routing comparisons**.
- Verify quote fidelity, required issue categories, and factual errors separately. Report invented facts, lost conflicts, ignored corrections, and unsupported values. Do not describe mock agreement as live model accuracy.
- Cover complete requests, missing dates/manager, conflicts, corrections, relative dates, requested new permission, withdrawals, embedded instructions, filename mismatch, reversed dates, and unrelated messages.
- Exercise provider failure, refusal, interrupted output, invalid JSON/schema, fabricated quotes, retry exhaustion, and failed retry after prior success.
- Exercise unchanged reruns, changed source/configuration/policy, omitted documents, concurrent operators, stale completion, process interruption, expired lease recovery, partial queue visibility, and interrupted exports.
- Run a 2,000-document synthetic mock workload to verify bounded concurrency, durable progress, uniqueness, and queue consistency. Report measured behavior without claiming live-provider throughput.

## Deliverables and handover

- Replace the placeholder README with exact setup, intake, queue inspection, resume, retry, refresh, test, accuracy, and export commands.
- Produce `extractions.jsonl`, `queue.json`, `accuracy.md`, `request-evidence.json`, and `verification.md` under `deliverables/`.
- Record source/configuration provenance and `response_source` on outputs. Include a credential-redacted request generated by the actual adapter and document implemented response handling.
- Commit reproducible mock-generated examples. Live evaluation remains optional and must be separately labelled with its model/configuration and observed results.
- Document single-host SQLite operation, local-disk storage, external SSH/operator access, possible duplicate provider calls after crashes, and the distinction between mock verification and live observations.
- Preserve the existing Entire capture setup. At eventual submission, verify capture, commit and push to the default branch, and provide the root repository link; do not create manual checkpoints.

Implementation order: source-derived expectations → storage and CLI → provider and validation → routing → recovery/concurrency checks → deliverables and documentation.
