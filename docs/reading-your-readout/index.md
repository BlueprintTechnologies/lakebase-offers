# Reading Your Assessment

Your Lakebase Readiness Assessment answers one question: **which of your SQL workloads should migrate to Lakebase, in what order, and what will it save?**

The assessment produces three artifacts: an executive summary, a detailed scorecard, and a cost-benefit analysis. This section walks each artifact and explains what to do with what you see.

## Who reads what

| Role | Start here | What you are deciding |
| --- | --- | --- |
| **Executive sponsor** | [For Executives](executive.md) | Is the ROI real? Do we start a PoC? |
| **Data owner / domain lead** | [For Data Owners](data-owner.md) | Which workloads are mine and where do they land? |
| **Engineer / tech lead** | [For Engineers](engineer.md) | What exactly needs to change, and in what order? |

## How the scores work

Every workload in your platform was scored on three dimensions and assigned an **Opportunity Score** from 0 to 100:

```
Score = ((Pain × Business_Impact) / Complexity) × 10
Adjusted Score = Score × (1 + estimated_savings_pct / 100)
```

| Dimension | What it measures | Scale |
| --- | --- | --- |
| **Pain** | How much does this workload hurt today? (latency, scaling failures, cost overruns) | 1 (stable) → 10 (business-impacting outages) |
| **Business Impact** | How important is this workload to the business? | 1 (ad-hoc reporting) → 10 (revenue-critical, real-time) |
| **Complexity** | How hard is the migration? (SQL compatibility, UDFs, schema design) | 1 (simple SQL) → 10 (heavy PL/SQL, custom serialization) |

The adjusted score also incorporates the estimated cost savings for that workload, so a moderately complex workload with 60% savings can outrank a simpler workload with no savings.

## The three priority buckets

| Score | Label | What it means |
| --- | --- | --- |
| **≥ 25** | **Priority 1** | High confidence. Migrate now. Easiest wins with the strongest ROI. |
| **10–24** | **Evaluate** | Good fit, but needs prep work or refactoring first. Plan for Phase 2. |
| **< 10** | **Hold** | Not ready yet. Optimize current platform or revisit in 6–12 months. |

## The seven workload types

Every scored workload is also **classified** into one of seven fit categories:

| Type | Lakebase Fit | Migration Effort |
| --- | --- | --- |
| Analytics → Keep in Delta | Excellent | Low |
| Point Lookups + Cache | Excellent | Medium |
| Agent State / Feature Serving | Excellent | Medium |
| App Backends | Good | Medium |
| Real-time Join/Agg + Cache | Good | Medium |
| Heavy ETL/UDF | Risky | High — refactor first |

See [Workload Classifications](../scorecard-anatomy/workload-classifications.md) for what each type means and how to migrate it.

## What to read next

After reviewing this overview, follow the guide for your role:

- **[For Executives](executive.md)** — ROI, priority summary, PoC decision
- **[For Data Owners](data-owner.md)** — Workload triage, domain-level priorities, blocker review
- **[For Engineers](engineer.md)** — Specific migration steps, effort estimates, SQL compatibility checklist
