# Pain — How Much Does It Hurt Today?

**Outcome question:** *How much is this workload costing us in reliability, performance, or operational burden right now?*

Pain is the demand side of the migration equation. A high-pain workload has clear business pressure to change; a low-pain workload is a harder internal sell even if Lakebase would run it cheaper.

## What the assessor measures

The assessor collects the following signals to compute a Pain score:

| Signal | How it is collected | What high means |
| --- | --- | --- |
| **P95 query latency** | Query history from platform system tables | Queries regularly exceed SLA targets |
| **Query failure rate** | Failed or timed-out queries in the past 30 days | Reliability issues affecting users |
| **Concurrency queue depth** | Peak concurrent sessions and wait times | Scaling bottleneck; users wait for resources |
| **Scaling events** | Warehouse/cluster auto-scale triggers | Platform struggling to meet demand |
| **Cost spikes** | Compute cost variance (high variance = uncontrolled spend) | Unpredictable, runaway cost |
| **Manual intervention frequency** | Customer input during tech champion interview | Team spending time firefighting |

The Pain score is normalized to a 1–10 scale:

| Score | What it looks like |
| --- | --- |
| **1–3** | Stable. Queries run fast. Scaling is automatic. No user complaints. |
| **4–6** | Occasional slow queries. Manual scaling events. SLA near-misses. |
| **7–9** | Frequent timeouts. Scaling failures. Business impact (revenue loss, report delays). |
| **10** | System failing. Business halted. Emergency support costs. |

## Why Pain matters for the score

Pain appears in the numerator of the formula: `(Pain × Business_Impact) / Complexity`. A workload with zero pain has zero score regardless of how simple the migration would be — there is no internal pressure to move it. A workload with maximum pain can still score poorly if complexity is high, because the migration is risky.

The sweet spot for a PoC is Pain ≥ 7 + Complexity ≤ 4. That combination means: something is genuinely broken, and the fix is within reach.

## What "good" looks like

A Pain score of 7 or above indicates the workload is a strong migration candidate on its own merits — users are feeling it, and the business case is self-evident. You do not need to explain why migration matters; you need to explain when.

A Pain score below 4 does not mean migration is wrong. It means the ROI story is primarily about **cost savings**, not current suffering. Check the Business Impact and Complexity scores; if those are favorable, the case is "we can run this cheaper and simpler even though it works today."

## Improving Pain inputs

If a workload's Pain score seems lower than reality, two things can cause it:

1. **Short query history.** If the assessor only had 7–14 days of history, an infrequent but severe scaling failure may not have appeared. Re-run after 30+ days or provide your incident history during the tech champion interview.
2. **Non-query pain.** Operational pain (manual tuning, on-call escalations, brittle pipelines) does not appear in query system tables. Capture this during the tech champion interview; your account executive can adjust the score manually with that context.

## Related

- Scoring formula: [Anatomy of Your Scorecard](index.md)
- How complexity tempers pain: [Complexity](03-complexity.md)
- Migration playbook for high-pain/low-complexity workloads: [Analytics to Delta](../migration-playbooks/analytics-to-delta.md)
