# Executive Sponsor Learning Path

For CIOs, CFOs, VP of Engineering, and other decision-makers who need to understand the business case, risks, and expected outcomes of the Lakebase migration — without getting into technical implementation details.

## What you need to take away from the assessment

Your assessment report answers four business questions. Make sure you can answer each before deciding on Phase 2:

| Question | Where to find it |
| --- | --- |
| How much are we spending on our current data platform? | Cost section of your readout |
| What is the projected annual savings if we migrate? | Executive summary — "Cost Delta" row |
| Which workloads should we migrate first? | Priority 1 workloads list |
| What is the migration risk and effort? | Scorecard — Complexity dimension per workload |

For a walkthrough of each section: [Reading Your Readout — Executive View](../reading-your-readout/executive.md).

## The business case in three numbers

Every Lakebase migration opportunity has three numbers that define the business case:

1. **Current annual platform cost** — what you're paying today (licenses, compute, storage, support)
2. **Projected annual Lakebase cost** — estimated DBU consumption at current workload volumes
3. **Payback period** — migration investment ÷ annual savings

A well-scoped migration typically pays back in 12–18 months. Migrations with high platform cost and high Lakebase Opportunity Score can pay back in 6–9 months.

## Understanding the score

The Lakebase Opportunity Score is not a quality rating — it is a migration ROI signal:

- **High score (≥ 25):** High pain + high business impact + low complexity = migrate first
- **Mid score (10–24):** Worth evaluating; sequence after Priority 1 workloads
- **Low score (< 10):** Migration cost exceeds near-term benefit; defer

The score does **not** indicate how important the workload is to the business. A critical production workload can score low if it has high complexity (e.g., heavy stored procedure usage). Complexity means migration effort, not business value.

## Risk framework

| Risk | How it's managed |
| --- | --- |
| Data correctness during migration | Parallel run period: both platforms run simultaneously, outputs compared |
| Performance regression | Load testing against SLA targets before cutover |
| Compliance / access control gap | Trust Foundations review before any data moves |
| Rollback if migration fails | Source platform stays live until 72-hour monitoring passes |
| Team capacity | Migration pod model: dedicated team, not pulled from existing ops |

No source platform workload is decommissioned until a 72-hour error-free monitoring window is complete. See [Measuring Migration Success](../after-the-engagement/measuring-success.md).

## Timeline expectations

| Phase | Duration | Your involvement |
| --- | --- | --- |
| Free Assessment | 1–3 weeks | Kickoff + readout meetings |
| Free+ PoC | 2 weeks | PoC scope approval + go/no-go decision |
| Phase 2 — Wave 1 | 4–8 weeks | Weekly status; milestone sign-offs |
| Phase 2 — Wave 2+ | Per-workload | Quarterly steering review |

The 30/60/90 day plan your engagement lead delivers at the readout gives the full milestone timeline. [See the template](../after-the-engagement/30-60-90.md).

## What to expect at the readout meeting

The readout is a 60-minute working session, not a slide presentation. It covers:

1. **Portfolio summary** (10 min) — total workloads scored, priority distribution, projected savings
2. **Top PoC candidates** (15 min) — the 2–3 workloads with the best migration ROI
3. **Trust Foundations gaps** (10 min) — what needs to be in place before migration can start
4. **30/60/90 plan** (15 min) — week-by-week milestones
5. **Q&A / decision** (10 min) — go / no-go on Free+ PoC

Come prepared to answer: which workload would deliver the clearest business value if migrated first? That becomes the PoC target.

## Questions to ask your engagement lead

- What is the confidence interval on the projected savings? (The model uses conservative estimates by default.)
- Which Trust Foundations gaps are blocking migration, and how long do they take to close?
- What happens if the PoC performance doesn't meet SLA targets?
- How does this migration affect our existing Databricks Enterprise Agreement (if any)?
- What is Blueprint's role post-migration (steady state support)?

## Key terms for executives

| Term | Plain-language meaning |
| --- | --- |
| DBU (Databricks Unit) | The billing unit for Databricks compute; like a vCPU-hour, but standardized |
| Lakebase | Databricks' branded SQL query engine (SQL Warehouse + Delta Lake) |
| Delta Lake | The storage format that gives Databricks ACID transactions and time travel |
| Unity Catalog | Databricks' centralized access control and governance layer |
| Lakebase Opportunity Score | Blueprint's formula for migration ROI: (Pain × Business Impact) / Complexity |
| PoC (Proof of Concept) | A 2-week migration of one workload to validate performance and cost claims |
| Trust Foundations | The governance prerequisites Blueprint checks before migrating any workload |

Full glossary: [Glossary](../glossary.md).

## Related

- Reading your readout: [Executive View](../reading-your-readout/executive.md)
- 30/60/90 day plan: [After the Engagement](../after-the-engagement/30-60-90.md)
- What success looks like: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
- Security and compliance: [Security & Compliance](../security-and-compliance.md)
