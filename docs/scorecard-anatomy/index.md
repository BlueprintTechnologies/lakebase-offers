# Anatomy of Your Scorecard

Three dimensions combine to determine whether a workload should migrate to Lakebase, and in what order. Together they answer: **how much pain are we in, how much does it matter, and how hard is the move?**

Each page in this section covers one dimension, with:

- **The outcome question** shown in your scorecard and executive summary.
- **What the dimension actually measures** — the underlying signals the assessor collected.
- **Why it matters for migration** — what happens to the score if this dimension is low.
- **What "good" looks like** for this dimension.
- **Where to improve it** — the Trust Foundations playbook to follow.

## The three scoring dimensions

| # | Dimension | Outcome question | What it measures |
| --- | --- | --- | --- |
| 1 | [Pain](01-pain.md) | How much does this workload hurt today? | Latency, scaling failures, cost spikes, query failures |
| 2 | [Business Impact](02-business-impact.md) | How critical is this workload to the business? | Query frequency, user count, revenue exposure, SLA criticality |
| 3 | [Complexity](03-complexity.md) | How hard is the migration? | SQL dialect, UDF depth, schema complexity, data type alignment |

## The opportunity score formula

```
Raw Score = ((Pain × Business_Impact) / Complexity) × 10

Adjusted Score = Raw Score × (1 + estimated_savings_pct / 100)
```

The adjusted score folds in cost savings as a tiebreaker: a workload with moderate complexity but 60% savings potential will score higher than one with the same complexity and only 10% savings.

## Reading the score

A score of 0 on any dimension does not mean the workload is unmigrateable. It means that dimension has low supporting evidence — for example, a new workload with no query history will score low on Pain (we do not know how bad it is yet). Whether that is a problem depends on the dimension. Low Pain on a workload you know is business-critical is fine; low Business Impact on a workload driving real-time revenue is a signal to review the scoring inputs.

## Priority thresholds

| Score range | Priority | Recommended action |
| --- | --- | --- |
| **≥ 25** | Priority 1 | Migrate now. High confidence. Strong ROI. |
| **10–24** | Evaluate | Worth migrating. Needs prep or planning first. |
| **< 10** | Hold | Not ready. Address complexity or wait for pain to increase. |

## Critical blockers

Beyond the three dimensions, the assessor also flags **critical blockers** — issues that prevent migration regardless of score. A workload can score 95 and still be blocked. See [Critical Blockers](critical-blockers.md).

## Workload classifications

Every scored workload is also placed into one of seven **fit categories** based on its query patterns and data access needs. The classification tells you which migration playbook to follow. See [Workload Classifications](workload-classifications.md).

## Deferred signals

The assessor captures additional signals that do not roll into the Opportunity Score but appear in the detailed workload table. These are informational rather than decision-driving:

| Signal | Why it is not a headline score | Where it shows up |
| --- | --- | --- |
| Data quality | Nullability, type consistency, and freshness are addressed by your existing data quality program, not migration prep. | Engineer page findings table. |
| Query history depth | < 30 days of history reduces confidence; it does not change the score formula. | Score confidence label (High / Medium / Low). |
| Third-party tool dependency | Tools like Tableau, dbt, Informatica need connection string updates but do not affect workload migratability. | Blockers column, severity Low. |
