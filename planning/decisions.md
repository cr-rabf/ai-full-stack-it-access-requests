# Accepted implementation decisions

The user approved D1–D4 before Step 6 implementation.

- D1: Operators share one host and local disk. SQLite transactions and OS file
  locks coordinate work. Separate installations and network filesystems are unsupported.
- D2: The newest-started attempt is current, including while pending. Start order
  means SQLite's committed attempt sequence. Late older completions remain in
  history and cannot replace the current attempt.
- D3: Persist pending work before the provider call and completion in one transaction.
  An OS file lock identifies each active attempt. Resume claims unfinished work
  only when its lock is free. Completed work remains durable.
- D4: Reuse depends on source bytes, provider/model/request settings, prompt, schema
  and policy. Reuse unchanged completed successes and errors. Explicit retry always
  creates an attempt. Worker count, logging and export destination do not invalidate
  results. An identical active attempt is reused as pending, without another call.

Exports publish immutable generations through one atomic `current` symlink switch.
Readers comparing queue and extraction files must resolve `current` once and read
both files from that immutable generation. Root deliverable links are conveniences;
records carry generation IDs to expose accidental cross-generation comparisons.

D5 was approved by the user before Step 9: compare all 12 scalar fields for the
20 supplied messages and the authored paraphrase (252 comparisons), with exact
strings and explicit nulls and no normalization. Missing documents and failed or
schema-invalid records receive zero of 12 matches, including expected nulls.
Unexpected documents are reported separately without changing the denominator.
Routing and evidence checks are separate. Frozen rules and source-derived values
are in `deliverables/accuracy-rules.json` and `deliverables/expected-fields.json`.
