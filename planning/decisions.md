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

D5 remains open. No corpus accuracy normalization or denominator is adopted here.
