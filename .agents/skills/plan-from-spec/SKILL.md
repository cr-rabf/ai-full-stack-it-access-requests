---
name: plan-from-spec
description: Turns planning/spec.md into planning/plan.md before any code is written - ordered build steps, each naming the spec lines it meets and the test written first, with the test plan inside the plan. Use when asked to plan the build from the spec, or to write or fix the test plan.
---

# Plan from the spec

Write `planning/plan.md` from `planning/spec.md`. Write no application code and no tests in this
step: the plan is read and corrected by a person before anything is built.

## Read first

- `planning/spec.md`: the numbered requirements (R-01, R-02, ...) and how each is checked.
- `CHALLENGE.md`, `docs/requirements.md`, `materials/office-policy.md` and `snapshot.schema.json`:
  the sources the spec was written from.
- The request exports in `materials/requests/`: open the ones a test case uses, and read their
  `message` text.

## Write `planning/plan.md` with these four sections

1. **Choices.** The runtime, the interface (a CLI, a service or a web application), the test
   command, and how the model provider is called. One line each, with its reason.
2. **Steps, in build order.** A numbered list. Each step names the spec lines it meets
   (`R-03, R-07`), the test from the test plan that is written first and seen to fail, and what is
   true when the step is done. The first step builds the mock provider the tests use. Each test
   belongs to one step only, so every step has a test that fails until that step's code exists.
3. **Test plan.** A table, one row per case:

   | Case | Input | Mock response | Expected facts | Source of the expected facts | Spec lines |
   |---|---|---|---|---|---|

   - One row for each case in `docs/requirements.md` § Verification: a complete request, missing
     dates, conflicting details, embedded instructions, provider failure, an unchanged rerun and
     changed source content; then the paraphrased synthetic request, a refusal or interrupted
     response, and a failed retry after a prior success.
   - **Input** names the export file (or the new message you author) that shows the case. Find it by
     reading the messages.
   - **Mock response** says what the mock provider returns for that case: a reply saved under
     `tests/mock_responses/`, an error, or a cut-off reply. No test calls the real provider.
   - **Expected facts** are the field values, status, owner and next action the case must produce.
     Write them from the message text and the office policy, never from running the code.
   - **Source of the expected facts** quotes the words of the message and the policy rule they
     come from.
4. **Coverage.** Every spec line, each with the step that builds it and the test or check that
   shows it. A spec line with no step or no test is listed under "Not yet covered", with the reason.

## Before you finish

- Every spec line appears in § Coverage with a step and a test, or under "Not yet covered".
- Every expected fact has a quote from a message or the policy beside it.
- Every case of § Verification has its own row.
- No step and no test needs `API_KEY`.
- No test is named by two steps.

Where a spec line is unclear, say so in the plan and ask the person; do not guess a rule.
