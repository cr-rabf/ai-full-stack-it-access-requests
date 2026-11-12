# Block 1. Research: the brief as a spec

The brief is written as prose, across four files. Before you plan or write code, turn it into a
**spec**: a list of numbered requirements, each one sentence a test or an inspection can check,
each with the words of the brief it comes from and how you will check it. Block 2 plans from the
spec, and block 3 checks what Codex built against it, line by line. A requirement missing from the
spec is one nobody will build or check.

Start only after `python3 tools/check_prerequisites.py` prints `READY`
(`docs/00-prerequisites.md`).

## What to read

| File | What it gives the spec |
|---|---|
| `CHALLENGE.md` | the task, and the files you submit, each with what it must contain |
| `docs/requirements.md` | the operating context, record and review behaviour, and § Verification: the cases your tests must cover |
| `materials/office-policy.md` | the fields to extract, the five review-queue rules in order, processing and recovery |
| `snapshot.schema.json` | the record each extraction must match |
| `materials/requests/` | the 20 message exports; read three or four to see what the rules meet |

## Steps

1. Start Codex in the root of your clone: `codex`.
2. Ask Codex to read the four files and draft `planning/spec.md`. Your request says:
   - one numbered requirement per line, `R-01`, `R-02`, ..., each one testable sentence;
   - for each, the file and section it comes from, with the exact words quoted;
   - for each, how it will be checked: which test, which file to inspect, or which command to run;
   - nothing invented: a requirement the files do not state is not in the spec.

   <details><summary>An example request, if you want a starting point</summary>

   ```text
   Read CHALLENGE.md, docs/requirements.md, materials/office-policy.md and snapshot.schema.json.
   Write planning/spec.md: a table with columns ID, Requirement, Source, Check. One row per
   requirement, IDs R-01 onward. Requirement is one sentence that a test or an inspection can
   check. Source names the file and section and quotes the exact words. Check says how we will
   know it is met: the test, the file to inspect, or the command. Do not add anything the files
   do not say. Do not write any code.
   ```

   </details>

3. Read the draft against the files yourself. Codex misses requirements and merges two into one
   line. Check that these each have their own lines:
   - every fact the policy says to extract, and the rules for missing, conflicting and corrected values;
   - each of the five review-queue rules, in the policy's order;
   - each processing and recovery rule: errors, retries, hashes, reruns, changed input, history;
   - each file `CHALLENGE.md` asks you to submit;
   - each case `docs/requirements.md` § Verification lists.
4. **Research what the text leaves unclear.** Ask Codex to list every place where two readings are
   possible, or where a term is not defined. For each, look it up (in the files first, then in the
   documentation of the tool or standard it names) and write what you found. Add a section
   `## Open questions` to the spec: each question, what you found, and what stays open. Do not turn
   an open question into a requirement by guessing.
5. Commit the spec:

   ```bash
   git add planning/spec.md
   git commit -m "Spec: the brief as numbered requirements"
   ```

## What is on disk at the end

`planning/spec.md`, committed: the requirements table, then `## Open questions`.

## How to tell it is right

- Every row quotes the words it comes from, and you found those words in the file it names.
- Every row's check could fail: "the code is correct" is not a check; "the test for IT-0nn gives
  status needs-information" is.
- Each case of `docs/requirements.md` § Verification and each of the five queue rules has its own row.
- `git log --oneline -1` shows the spec commit.

Codex's summary of what it wrote is not the check. Open `planning/spec.md` and read it.
