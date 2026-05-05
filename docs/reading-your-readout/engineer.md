# For Engineers

The engineer section of your Lakebase Readiness Assessment is the working surface. It is where you go after the data owner has decided priorities and you are now executing the migration.

This guide is intentionally short. The per-workload migration work happens in the [Migration Playbooks](../migration-playbooks/index.md). This page maps the scorecard sections to the right playbook and the right order.

## The score distribution

A histogram shows how your assessed workloads are distributed across the 0-100 Opportunity Score range. Use this for a quick sanity check before diving in.

If the histogram is strongly left-skewed (most workloads scoring < 10), your estate has a complexity problem — likely heavy ETL, legacy SQL syntax, or deep UDF dependencies. The right first step is a refactoring sprint, not a migration. See [Heavy ETL — Refactor First](../migration-playbooks/heavy-etl.md).

If the histogram is bimodal — a cluster at 80+ and another at < 10 — you have clean quick wins alongside genuinely hard workloads. Migrate the high cluster first while planning refactoring for the low cluster.

## Findings by dimension

A bar chart breaks the remediation backlog by which scoring dimension each blocker belongs to. The three dimensions are Pain, Business Impact, and Complexity. Blockers are always on the Complexity side.

The right work order is: **critical blockers first** (compliance gates, unsupported data types), then **complexity reducers** (UDF rewrites, schema simplification), then **migration execution**.

## The full workload table

Every assessed workload is listed with:

- **Opportunity Score and priority bucket**
- **Pain / Business Impact / Complexity** scores (1–10)
- **Workload type** (Analytics, Point Lookup, App Backend, etc.)
- **Blockers** (specific, actionable flags)
- **Suggested migration approach** (one-line summary)
- **Estimated effort** (Low 1–2 weeks / Medium 2–6 weeks / High 6–12 weeks)

Filter to **Priority 1, no blockers** to get your immediate migration list. Filter to **Evaluate, complexity < 6** to get the next wave after a brief refactoring sprint.

## The SQL compatibility report

For each workload, the assessor ran a compatibility check against the Lakebase SQL dialect. The compatibility report flags:

| Flag | Severity | What to do |
| --- | --- | --- |
| **Proprietary function** | Medium | Rewrite using Databricks built-in equivalent. See [SQL Compatibility Check](../trust-foundations/sql-compatibility.md). |
| **Unsupported syntax** | High | Refactor the query. Databricks SQL reference is authoritative. |
| **Data type mismatch** | Medium | Map source type to Delta type. Common: `VARIANT → STRUCT`, `NUMBER(p,s) → DECIMAL(p,s)`. |
| **Stored procedure / UDF call** | High | Rewrite as Python Spark UDF or pure Databricks SQL. |
| **Semi-structured column** | Low | Use Databricks `:`  and `::` operators for JSON/XML column access. |
| **Custom serialization** | Critical | Binary or proprietary formats need format conversion before migration. |

Critical and High flags must be resolved before a workload can be migrated. Medium flags can often be resolved in parallel with the migration sprint.

## The migration checklist

For each workload in your PoC scope, the assessor generates a migration checklist:

```
[ ] 1. Validate source schema against Delta type system
[ ] 2. Run SQL compatibility check, resolve all High flags
[ ] 3. Apply Unity Catalog grants (replicate source ACLs)
[ ] 4. Run initial data load (full or incremental)
[ ] 5. Validate row counts and key distributions
[ ] 6. Run query regression tests (source vs. Lakebase outputs)
[ ] 7. Validate P95 latency against SLA target
[ ] 8. Update connection strings in downstream apps/tools
[ ] 9. Monitor for 72 hours before decommissioning source
```

Follow this checklist for each workload. Do not skip the 72-hour monitoring window — this is when late-arriving data and edge-case queries typically surface.

## Re-running the assessment

The assessor is a local CLI — your account executive has the config. Re-running it does not overwrite prior results; each run generates a new output directory. Most teams re-run monthly during active migration to track progress and catch newly high-pain workloads.

## What to do with this page

1. **Open the full workload table.** Filter to Priority 1, no blockers.
2. **For each workload in your PoC list**, open the matching [Migration Playbook](../migration-playbooks/index.md) and walk the steps.
3. **For each blocker**, open [Trust Foundations](../trust-foundations/index.md) and close the blocker before attempting migration.
4. **Use the SQL compatibility report** to estimate the query rewrite effort. If a workload has more than 5 High flags, re-scope the PoC to a simpler candidate.
5. **After each workload is live**, mark it complete in your tracking sheet and use the [measuring success](../after-the-engagement/measuring-success.md) guide to validate outcomes.

The work is well-defined and incremental. Each migrated workload reduces your platform spend, simplifies your estate, and builds the patterns your team needs for the next wave.
