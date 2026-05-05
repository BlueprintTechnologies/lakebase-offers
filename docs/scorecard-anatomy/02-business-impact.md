# Business Impact — How Critical Is It?

**Outcome question:** *How important is this workload to the business — and who is depending on it right now?*

Business Impact is the second numerator dimension. It captures whether a workload is strategically important enough to justify migration investment. A high-impact workload failing is a business event; a low-impact workload failing is an inconvenience.

## What the assessor measures

| Signal | How it is collected | What high means |
| --- | --- | --- |
| **Query frequency** | Queries per day from platform history | Workload is actively and regularly used |
| **Unique user count** | Distinct users or service accounts running queries | Wide organizational dependency |
| **Downstream consumer count** | Pipelines, dashboards, or APIs that depend on this workload | Failure has a blast radius |
| **Peak concurrency** | Max simultaneous sessions against this workload | Business critical times have high load |
| **Business hours concentration** | % of queries during core business hours | Humans, not batch jobs, depend on it |
| **Revenue or operational flag** | Customer input during tech champion interview | Directly tied to revenue or core operations |

Business Impact is normalized to a 1–10 scale:

| Score | What it looks like |
| --- | --- |
| **1–3** | Ad-hoc report. Data scientist exploration. Nice-to-have. Infrequent, low user count. |
| **4–6** | Department dashboard. Internal analytics. Regular use by a defined team. |
| **7–9** | Customer-facing feature. Real-time operations. Revenue-adjacent. Multi-team dependency. |
| **10** | Core product. 24/7 availability required. SLA breach = customer churn or regulatory exposure. |

## Why Business Impact matters for the score

Business Impact is the second numerator: `(Pain × Business_Impact) / Complexity`. A workload with high pain but low business impact will score lower than you might expect — the right response to a broken internal ad-hoc report might be to retire it, not migrate it.

The combination of high Pain + high Business Impact is the clearest signal for Priority 1. Those workloads are hurting the business and the business cares deeply. The migration case writes itself.

## What "good" looks like

A Business Impact score ≥ 7 means migration has visible executive sponsorship built in — someone is already feeling the pain at the leadership level. Use this as a selling point when proposing the PoC: "this is the workload your VP of Sales complains about every Monday."

A Business Impact score of 3–5 means the workload is real and used, but the migration ROI story is primarily about cost reduction and future-proofing. Present it alongside higher-impact workloads so the PoC scope has a mix.

## Improving Business Impact inputs

Business Impact is harder to auto-detect than Pain. Two common gaps:

1. **Revenue linkage is implicit.** A query that populates a dashboard used by the sales team to set quotas is revenue-critical, but the assessor cannot detect that from query history alone. Capture it during the tech champion interview.
2. **Service accounts mask real user counts.** If a pipeline service account runs 1000 queries/day on behalf of 200 downstream users, the user count appears as 1. Ask your account executive to adjust the score for service-account-mediated workloads.

## Related

- Scoring formula: [Anatomy of Your Scorecard](index.md)
- High-impact workload playbooks: [Point Lookups + Cache](../migration-playbooks/point-lookups.md), [App Backends](../migration-playbooks/app-backends.md)
- For executives interpreting impact scores: [For Executives](../reading-your-readout/executive.md)
