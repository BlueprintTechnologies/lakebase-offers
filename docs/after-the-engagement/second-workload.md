# Scaling to More Workloads

After the first production migration, the program accelerates. Your team has the runbook, the patterns, and the confidence. This page covers what carries over from the first migration and what you need to do differently as you expand.

## What carries over from the first migration

**The runbook.** The per-workload migration checklist is now proven. Every subsequent migration follows the same template; the first migration was practice.

**The Unity Catalog structure.** Your catalog, schemas, and access model are established. New workloads slot into the existing structure — no setup overhead.

**The validation suite.** The correctness queries you wrote for the first migration are the template for all subsequent migrations. Parameterize them and reuse.

**The pod rhythm.** Daily standup, weekly sponsor report, monthly re-assessment. This cadence is now operational and should not change.

**The trust.** After one successful production migration, your executive sponsor is a believer. Use this to move faster in Phase 2 — less validation overhead, more migration velocity.

## What to do differently in Phase 2

**Parallelize.** If you have two data engineers, run two workload sprints simultaneously. The patterns are known; parallelism is now the bottleneck, not learning.

**Start Evaluate workloads earlier.** Evaluate workloads require refactoring, which takes 1–2 weeks before migration can begin. Start the refactoring sprint while Phase 1 workloads are in their monitoring window — this prevents a gap between Phase 1 completion and Phase 2 migration start.

**Engage the business owner earlier.** For high-impact workloads (Business Impact ≥ 8), bring the business owner into the sprint at day 3, not day 10. They catch semantic errors that engineers miss ("this number looks right but it's wrong because we changed the fiscal year definition").

**Automate validation.** If you migrated 3 workloads manually, the fourth is the time to write a Python script that runs the correctness queries automatically and diffs the results. This reduces validation time from hours to minutes.

## The second workload type

Your first migration established patterns for one workload type (e.g., Analytics to Delta). The second phase is the right time to introduce a different workload type.

**Recommended second-type sequence:**

| First migration type | Recommended second type | Why |
| --- | --- | --- |
| Analytics to Delta | Point Lookups + Cache | Different pattern; teaches caching design |
| Point Lookups | App Backends | Same caching layer; extends ACID knowledge |
| App Backends | Analytics to Delta | Complements transactional with reporting |
| Heavy ETL (post-refactor) | Analytics to Delta | Cleanest path after refactoring sprint |

Introducing a second workload type in Phase 2 builds the team's range and reduces the risk of becoming dependent on a single migration pattern.

## Re-running the assessment for Phase 2

Before starting Phase 2, re-run the assessor:

```bash
lakebase-assess run --config my-assessment.yaml --output-dir ./phase2-assessment
```

Why re-run? Three things change after Phase 1:

1. **Pain scores increase** for workloads still on the source platform. As more data and users shift to Lakebase, the source platform becomes less maintained — pain increases.
2. **New workloads may appear.** Production query patterns change; new workloads surface in the assessment.
3. **Hold workloads may have upgraded.** If you resolved a blocker (compliance review completed, UDF rewritten), a Hold workload may now score as Evaluate or Priority 1.

The re-assessment takes the same time as the first but produces a tighter, more current backlog.

## Managing source platform decommission

As workloads migrate, you need a plan for retiring the source platform.

**Decommission sequence:**

1. **Domain complete:** All workloads in a domain are migrated and stable on Lakebase (30 days in production)
2. **Consumer confirmed:** All downstream consumers (dashboards, APIs, pipelines) have updated connection strings
3. **Access removed:** No production service accounts have write access to the source schema
4. **Schema archived:** A final snapshot of the source schema is archived in object storage for audit purposes (Delta export + Parquet)
5. **Platform notified:** Account team at the source platform is notified of the decommission (triggers contract review or termination)

**Timeline:** Plan for 60 days between "last workload migrated" and "source platform decommissioned." This buffer allows for late-discovered dependencies and ensures monitoring time.

**Cost savings realization:** Savings are not fully realized until the source platform contract is terminated or reduced. Most platforms bill by cluster or warehouse; partial decommission still incurs the platform fee. Target full decommission of at least one source platform by day 90.

## When to bring Blueprint back in

For Phase 2 and beyond, most customers operate independently. Situations where bringing Blueprint back accelerates the program:

- **High Evaluate workload volume.** If Phase 2 has > 5 Evaluate workloads, a second Blueprint sprint can run refactoring and migration in parallel with your team's ongoing work.
- **New source platform.** If Phase 2 includes a platform the first migration did not cover (e.g., you migrated Snowflake in Phase 1 and now have Teradata), a short re-engagement scopes the new platform correctly.
- **Optimization phase.** After all workloads are migrated, a Blueprint performance review often finds 15–25% additional savings through warehouse right-sizing, caching configuration, and query optimization.
- **Governance maturity.** If your Phase 3 goals include Unity Catalog metadata management, data quality SLAs, or AI/BI deployment, Blueprint can scope and deliver these as follow-on engagements.

## Related

- The full migration timeline: [30/60/90 Day Plan](30-60-90.md)
- How to validate each migrated workload: [Measuring Migration Success](measuring-success.md)
- Re-running the assessor: [ACCELERATOR.md](../../ACCELERATOR.md)
