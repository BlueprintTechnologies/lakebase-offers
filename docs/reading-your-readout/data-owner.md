# For Data Owners

The detailed scorecard is your working surface as a domain lead or data steward. It answers two questions:

1. **Which of my workloads land in which priority bucket, and why?**
2. **Are the workloads my business depends on the ones that are easiest to migrate?**

This guide walks the scorecard and explains what to do with each section.

## The workload priority table

The scorecard opens with a full table of every assessed workload, sorted by Opportunity Score descending. Each row shows:

- **Workload name.** The query pattern or workload identifier.
- **Opportunity Score.** 0–100. Higher is better. See [Anatomy of Your Scorecard](../scorecard-anatomy/index.md) for the formula.
- **Priority bucket.** Priority 1, Evaluate, or Hold.
- **Pain / Impact / Complexity.** The three input dimensions (1–10 each).
- **Estimated monthly savings.** Dollar delta for this workload.
- **Workload type.** The fit category (Analytics, Point Lookup, App Backend, etc.).
- **Blockers.** Any migration blockers identified (compliance flags, unsupported functions, custom serialization).

Sort by **Priority 1** first, then **Estimated monthly savings** descending. That order is your migration backlog.

## The domain breakdown

If your platform organizes data into domains or schemas, the scorecard breaks scores out by domain. This surface answers: "is the problem evenly distributed, or is one domain disproportionately complex?"

A domain with a high average score and low complexity is your fastest PoC candidate. A domain with high pain but high complexity needs a refactoring sprint before migration.

## The pain-vs-complexity scatter

The most useful tile for prioritization. Each dot is one workload. The horizontal axis is complexity (1–10); the vertical axis is pain (1–10).

The conversation this tile drives: **your most painful workloads are not always the easiest to migrate.** Workloads in the top-left quadrant (high pain, low complexity) are your Priority 1 candidates — fix the most pain with the least effort. Workloads in the top-right (high pain, high complexity) need refactoring first; the pain is real but the migration is risky without prep.

| Quadrant | Meaning | Action |
| --- | --- | --- |
| High pain, low complexity (top-left) | Quick wins. Strong ROI, easy migration. | PoC these first. |
| High pain, high complexity (top-right) | Refactor first, then migrate. Pain justifies the effort. | Phase 2, with refactoring sprint. |
| Low pain, low complexity (bottom-left) | Easy migration but low urgency. | Migrate in bulk after quick wins. |
| Low pain, high complexity (bottom-right) | High effort, low ROI. | Hold. Revisit in 12 months. |

## The workload type distribution

A breakdown of your workloads by the seven fit categories:

| Type | Count | Priority 1 % | Avg. Savings |
| --- | --- | --- | --- |
| Analytics → Delta | N | XX% | XX% |
| Point Lookups | N | XX% | XX% |
| App Backends | N | XX% | XX% |
| Agent State | N | XX% | XX% |
| Real-time Agg | N | XX% | XX% |
| Heavy ETL | N | XX% | XX% |
| Feature Serving | N | XX% | XX% |

Heavy ETL workloads are the ones most likely to be in the Hold bucket. If a large share of your estate is Heavy ETL, the program starts with a refactoring sprint. See [Migration Playbooks — Heavy ETL](../migration-playbooks/heavy-etl.md).

## The blocker summary

Any workload with a migration blocker is flagged. Common blockers and their resolution:

| Blocker | What it means | How to resolve |
| --- | --- | --- |
| **PII masking required** | Table contains PII that must be masked before migration | Apply Unity Catalog column masks before cutover. See [Compliance & Governance](../trust-foundations/compliance.md). |
| **Unsupported SQL function** | A function used in this workload has no direct Lakebase equivalent | Rewrite using the Databricks SQL function reference. See [SQL Compatibility Check](../trust-foundations/sql-compatibility.md). |
| **Heavy UDF dependency** | The workload calls stored procedures or UDFs with custom logic | Rewrite as Python/Spark UDFs or refactor to pure SQL. High effort. |
| **Compliance gating** | A regulatory or policy requirement blocks cutover | Work with your compliance team. See [Security and Compliance](../security-and-compliance.md). |
| **Schema complexity** | Deeply nested joins, custom serialization, or non-standard types | Schema redesign required before migration. Medium effort. |
| **Low query history** | < 30 days of history; score confidence is Low | Re-run the assessment after 30+ days of production traffic. |

If more than 20% of your Priority 1 workloads have blockers, address blockers before scheduling the PoC. Blueprint can help scope the blocker resolution as a pre-PoC sprint.

## The cost delta by workload

The scorecard shows estimated savings per workload in a table sorted by dollar impact. This is the number your CFO will want. The methodology:

- **Current cost** is modeled from your query history, compute usage, and storage (using list rates unless you provided custom pricing).
- **Lakebase cost** is projected using DBU pricing and storage, adjusted for serverless efficiency.
- **Confidence** (High / Medium / Low) reflects the quality of query history available.

If a workload's confidence is Low, add a 20–30% uncertainty buffer to the savings estimate before presenting to finance.

## What to do with this page

1. **Pick the top 3 Priority 1 workloads** with Low or no blockers. Those are the PoC candidates.
2. **For each blocker-flagged workload**, route the resolution to the right owner: compliance → your data governance team; SQL functions → your data engineering team; UDF rewrites → your application engineering team.
3. **Look at the domain breakdown.** If one domain is uniformly complex, consider scoping the PoC to a different domain that has cleaner data.
4. **Hand the [engineer page](engineer.md)** to the technical team with the list of PoC workloads. They will validate SQL compatibility and size the migration effort.

The teams that succeed here do not try to migrate everything at once. They pick one domain, one workload type, and one clear Priority 1 candidate — prove it works, then expand. The scatter and the domain breakdown together make that choice defensible.
