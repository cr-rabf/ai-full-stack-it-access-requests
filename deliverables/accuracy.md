# Source-grounded accuracy evaluation

Observed configuration: saved mock responses from `tests/mock_responses/evaluation-config.json`.
These observations exercise fixture plumbing and deterministic policy, not live model accuracy.
The Anthropic HTTP adapter is separately contract-tested through fake transport; no live call was made.

Rules approved by the user and frozen before scoring: 12 scalar fields × 21 messages = 252 comparisons.
Strings compare exactly, including case and whitespace. Dates have no additional normalization.
A successful explicit null matches only an expected null. Missing documents and failed, unfinished,
source-mismatched or schema-invalid records receive zero of 12 matches, even for expected nulls.
Unexpected documents are reported separately; they do not change the denominator. Routing and
evidence checks are separate and do not increase the accuracy denominator.

Observed scalar matches: **252/252 (100.00%)**.
Factual errors: 0; routing differences: 0; evidence differences: 0.
Unexpected documents: [].

Frozen expectation SHA-256: `d71e1186057c2122c04df7905f62b2bbf3c46555cd6bdada052eeb09b4b8458f`.
Frozen rules SHA-256: `81c60a5c9a65683ebfbe94f0f5093082633de5c9120c12d7b643a11fcf114ebe`.

Reproduce from the repository root after mocked intake of the corpus and paraphrase:

```bash
env -u API_KEY python3 -m access_request accuracy --records deliverables/extractions.jsonl --report deliverables/accuracy.md
```

Expected fields below were transferred from the independent F001–F021 source ledger before scorer
implementation. [expected-fields.json](expected-fields.json) contains every exact evidence quote,
source hash and expected route. [accuracy-rules.json](accuracy-rules.json) contains the frozen rules.
Null expectations reflect review of the full source and policy; a short quote alone cannot prove absence.

| Document | Expected scalar facts |
|---|---|
| IT-001.json | `request_id="IT-001"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Maya Chen"`; `team="Analytics"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="checking the weekly conversion dashboard with the new event definition changes"`; `start_date="2026-10-23"`; `end_date="2026-11-06"`; `manager="Priya Shah"` |
| IT-002.json | `request_id="IT-002"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Owen Reed"`; `team="Payments"`; `system="Ledger"`; `environment="production"`; `permission="write"`; `business_purpose="make the corrections at the time of our scheduled maintenance and then check the totals against the settlement report"`; `start_date="2026-10-24"`; `end_date="2026-10-25"`; `manager="Elena Park"` |
| IT-003.json | `request_id="IT-003"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Lina Gomez"`; `team="Customer Success"`; `system="Beacon"`; `environment=null`; `permission=null`; `business_purpose="customer renewal review"`; `start_date=null`; `end_date=null`; `manager="Priya Shah"` |
| IT-004.json | `request_id="IT-004"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Theo Malik"`; `team="Quality Engineering"`; `system="Atlas"`; `environment=null`; `permission="read"`; `business_purpose="understand why the nightly quality report shows different counts from the release checklist"`; `start_date="2026-10-23"`; `end_date="2026-10-30"`; `manager="Nia Patel"` |
| IT-005.json | `request_id="IT-005"`; `request_date="2026-10-22"`; `kind="withdrawal"`; `requester="Ava Brooks"`; `team="Design"`; `system=null`; `environment=null`; `permission=null`; `business_purpose="The project that triggered my request has been cancelled so now there is no work for me to do."`; `start_date=null`; `end_date=null`; `manager="Elena Park"` |
| IT-006.json | `request_id="IT-006"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Finn Lee"`; `team="Platform"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="look at deployment metrics and compare them against release notes before service review"`; `start_date="2026-10-23"`; `end_date="2026-10-24"`; `manager="Nia Patel"` |
| IT-007.json | `request_id="IT-007"`; `request_date="2026-10-22"`; `kind="change"`; `requester="Grace Tan"`; `team="Developer Experience"`; `system="Forge"`; `environment="staging"`; `permission="write"`; `business_purpose="updating starter project templates"`; `start_date="2026-10-24"`; `end_date="2026-10-28"`; `manager="Nia Patel"` |
| IT-008.json | `request_id="IT-008"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Noah Kim"`; `team="Finance"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="check the sample billing total vs forecasting workbook before month end rehearsal"`; `start_date="2026-10-25"`; `end_date="2026-10-31"`; `manager="Priya Shah"` |
| IT-009.json | `request_id="IT-009"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Isla Morgan"`; `team="Support"`; `system="Beacon"`; `environment="staging"`; `permission="read"`; `business_purpose="go through example support cases before updating our troubleshooting guide"`; `start_date="2026-10-26"`; `end_date="2026-10-29"`; `manager=null` |
| IT-010.json | `request_id="IT-010"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Ben Carter"`; `team="Operations"`; `system="Ledger"`; `environment="production"`; `permission="read"`; `business_purpose="compare the daily reconciliation report to the entries that the operations folks see"`; `start_date="2026-10-27"`; `end_date=null`; `manager="Elena Park"` |
| IT-011.json | `request_id="IT-011"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Zoe Adams"`; `team="Research"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="looking at sample experiment records to get ready for our team walkthrough"`; `start_date=null`; `end_date=null`; `manager="Priya Shah"` |
| IT-012.json | `request_id="IT-012"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Ravi Shah"`; `team="Infrastructure"`; `system="Forge"`; `environment="staging"`; `permission="admin"`; `business_purpose="configuration migration rehearsal before planning the wider rollout"`; `start_date="2026-10-26"`; `end_date="2026-10-27"`; `manager="Nia Patel"` |
| IT-013.json | `request_id="IT-013"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Emma Wilson"`; `team="Compliance"`; `system="Beacon"`; `environment="production"`; `permission="read"`; `business_purpose="review account activity records to help with internal audit"`; `start_date="2026-10-28"`; `end_date="2026-10-30"`; `manager="Elena Park"` |
| IT-014.json | `request_id="IT-014"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Lucas Brown"`; `team="Sales Operations"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="demo of the new territory report for sales leads"`; `start_date="2026-11-05"`; `end_date="2026-11-02"`; `manager="Priya Shah"` |
| IT-015.json | `request_id="IT-015"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Mia Davis"`; `team="Learning"`; `system="Beacon"`; `environment="staging"`; `permission="read"`; `business_purpose="make sure that the sample conversations in the examples I'm building match up to the exercise handout for the Support onboarding workshop"`; `start_date="2026-10-29"`; `end_date="2026-10-31"`; `manager="Elena Park"` |
| IT-016.json | `request_id="IT-061"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Alex Turner"`; `team="Platform"`; `system="Forge"`; `environment="staging"`; `permission="read"`; `business_purpose="looking at the example pipeline runs to figure out why the starter project takes longer to build some of the time"`; `start_date="2026-10-26"`; `end_date="2026-10-28"`; `manager="Nia Patel"` |
| IT-017.json | `request_id="IT-017"`; `request_date="2026-10-22"`; `kind="other"`; `requester="Chloe Martin"`; `team="Communications"`; `system=null`; `environment=null`; `permission=null`; `business_purpose="Where can we find the access request form?"`; `start_date=null`; `end_date=null`; `manager=null` |
| IT-018.json | `request_id="IT-018"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Daniel Wright"`; `team="Data Engineering"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="reviewing our sample dataset we use during our weekly analyst workshop"`; `start_date="2026-10-27"`; `end_date="2026-11-03"`; `manager="Priya Shah"` |
| IT-019.json | `request_id="IT-019"`; `request_date="2026-10-22"`; `kind="change"`; `requester="Sara Ahmed"`; `team="Customer Operations"`; `system="Beacon"`; `environment="production"`; `permission="read"`; `business_purpose="reviewing the daily exception report"`; `start_date="2026-10-28"`; `end_date="2026-11-04"`; `manager="Elena Park"` |
| IT-020.json | `request_id="IT-020"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Ethan Clark"`; `team="Product"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="look at some sample usage records before I draft the summary on feature adoption"`; `start_date="2026-10-29"`; `end_date="2026-11-02"`; `manager=null` |
| IT-021.json | `request_id="IT-021"`; `request_date="2026-10-22"`; `kind="new"`; `requester="Maya Chen"`; `team="Analytics"`; `system="Atlas"`; `environment="staging"`; `permission="read"`; `business_purpose="check weekly conversion dashboard totals"`; `start_date="2026-10-23"`; `end_date="2026-11-06"`; `manager="Priya Shah"` |

Detailed observations and factual differences:

```json
{
  "matched": 252,
  "total": 252,
  "accuracy": 1.0,
  "factual_errors": [],
  "routing_errors": [],
  "evidence_errors": [],
  "unexpected_documents": [],
  "response_sources": [
    "mock"
  ],
  "provider_configurations": [
    {
      "provider": "mock"
    }
  ]
}
```

The hand-authored mocks encode known facts. Their match rate does not establish extraction
quality on fresh live responses, generalization, provider latency or throughput.
