# Standing Up Your Migration Pod

The migration pod is the small, dedicated team that executes Phase 2 and beyond. Getting the pod structure right in week 1 is what separates programs that complete from programs that stall.

## Pod composition

| Role | Responsibility | Time commitment |
| --- | --- | --- |
| **Pod lead** | Plans sprints, removes blockers, owns reporting to sponsor | 50–100% during active migration |
| **Data engineer (1–2)** | Executes migration sprints: schema migration, query rewrites, data validation | 100% during sprint, 25% ongoing |
| **Platform admin** | Databricks workspace, Unity Catalog grants, networking | 25% during migration, 10% ongoing |
| **Data owner / business rep** | Validates business semantics; signs off on query output correctness | 20% during sprint |
| **Executive sponsor** | Decision authority; unblocks cross-team dependencies | Weekly 30-min review |

For small programs (< 10 workloads), the pod lead and data engineer can be the same person. For large programs (> 25 workloads), two data engineers running parallel sprints is more efficient than one running sequentially.

## The pod's tools

| Tool | Use |
| --- | --- |
| **lakebase-assess** | Re-run assessments; track score progress; validate new workloads |
| **Databricks workspace** | All Lakebase SQL, notebooks, jobs, and monitoring |
| **Unity Catalog** | Access control, data governance, lineage |
| **Git repository** | Version-control migration runbooks, query rewrites, validation scripts |
| **Sprint tracking (Linear, Jira, or similar)** | One ticket per workload migration; blockers tracked as linked tickets |
| **Savings dashboard** | Weekly savings-to-date reported to executive sponsor |

## The weekly rhythm

**Daily standup (15 minutes):**
- What did each pod member complete yesterday?
- What are they working on today?
- Are there any blockers?

The pod lead takes every blocker as their action item. Blockers that cannot be resolved within 24 hours are escalated to the executive sponsor.

**Weekly sprint review (1 hour):**
- Demo each workload migrated that week (5 min per workload: show the query working, show the cost delta)
- Review blockers resolved and open
- Confirm next sprint workloads
- Report savings-to-date to executive sponsor (via written summary if they are not in the review)

**Monthly assessment re-run:**
- Re-run `lakebase-assess` against any remaining source platforms
- Update the priority backlog with new scores
- Identify any newly high-pain workloads that should be accelerated

## The per-workload sprint template

Each workload migration is a sprint. Copy this template as a ticket in your tracking tool:

```
Workload: [name]
Priority: [Priority 1 / Evaluate]
Type: [Analytics / Point Lookup / App Backend / etc.]
Source Platform: [Snowflake / Oracle / etc.]
Estimated Effort: [Low / Medium / High]
Assigned: [data engineer name]

Pre-conditions:
[ ] SQL compatibility check complete
[ ] Access control review complete
[ ] Compliance review complete (if PII/regulated)
[ ] Data quality baseline captured

Migration steps:
[ ] Schema migrated to Delta (CREATE TABLE)
[ ] Data loaded (initial full load or incremental)
[ ] Row counts validated
[ ] Query regression tests passed
[ ] P95 latency validated against SLA
[ ] Connection strings updated in downstream apps/tools
[ ] 72-hour monitoring window complete

Sign-off:
[ ] Data owner has approved query output correctness
[ ] Executive sponsor notified of go-live
[ ] Source workload decommissioned (or parallel-run end date set)

Cost result:
Source platform monthly cost: $____
Lakebase monthly cost: $____
Monthly savings: $____
```

## Sprint cadence

**Priority 1 workloads:** 1–2 workloads per 2-week sprint (one data engineer, full-time)

**Evaluate workloads:** 1 workload per 2-week sprint — the first week is refactoring, the second is migration and validation

**Hold workloads:** Do not start until they have been re-assessed and score ≥ 10

## Reporting to executive sponsors

A weekly savings-to-date summary keeps executive sponsors engaged without requiring them to dig into technical details:

```
Lakebase Migration: Week [N] Update

Workloads migrated to date: [X] of [Y] in scope
Production on Lakebase: [N] workloads
Measured monthly savings: $[X]K (vs. $[Y]K projected)
Source platforms decommissioned: [list]

This week:
+ Migrated [workload name]: $[X]K/month savings
+ Resolved [blocker]: [description]

Next week:
→ [workload name] migration sprint begins
→ [dependency] needed from [team] by [date]

Blockers:
⚠ [list any open blockers, owner, and deadline]
```

Keep this to one page or one Slack message. The savings number is the headline.

## Handoff to steady state

When the migration program completes (or transitions from active migration to optimization), the pod transitions to a lighter maintenance mode:

- Monthly assessment re-run to catch new workloads or newly high-pain workloads
- Quarterly cost review (actual vs. projected savings)
- Platform admin handles ongoing Unity Catalog governance
- Data engineers return to normal project work; one is designated as the Lakebase SME for future migrations

The migration pod is a temporary, focused team. Its success metric is making itself unnecessary.

## Related

- Sprint milestone checkpoints: [30/60/90 Day Plan](30-60-90.md)
- Validating each migrated workload: [Measuring Migration Success](measuring-success.md)
- Expanding to more workloads: [Scaling to More Workloads](second-workload.md)
