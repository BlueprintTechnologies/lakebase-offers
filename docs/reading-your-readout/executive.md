# For Executives

The executive summary of your Lakebase Readiness Assessment answers one question: **is migrating to Lakebase worth doing, and if so, where do we start?**

This guide walks the executive summary top to bottom and tells you what to do with what you see.

## The opening summary

The executive summary opens with a plain-language paragraph naming your platform, the number of workloads assessed, the overall opportunity band, and the estimated annual savings. Read this first. The tables and charts below are the supporting evidence.

## The four top-line numbers

Four counters appear at the top of the summary:

- **Priority 1 workloads.** The count of workloads with Opportunity Scores ≥ 25. These are your migration quick wins — high confidence, low complexity, strongest ROI. If this number is greater than 3, you have enough to start a PoC immediately.
- **Estimated annual savings.** The projected cost delta between your current platform spend and the equivalent Lakebase spend, annualized. This is computed from your actual query history, not benchmark estimates. The methodology is in [Anatomy of Your Scorecard — Complexity](../scorecard-anatomy/03-complexity.md).
- **Workloads assessed.** The total count of workloads the assessor evaluated. This should match the scope set at kickoff. If it is lower, ask your account executive whether some platforms were unreachable.
- **Assessment date.** The date the assessment ran. Scores older than 90 days should be treated as directional rather than current; re-run before committing to a PoC scope.

## The opportunity bands

Your overall platform score falls into one of three bands:

| Band | Meaning |
| --- | --- |
| **Strong opportunity** (avg score ≥ 20) | Multiple Priority 1 workloads. A PoC will validate quickly. Recommend starting within 30 days. |
| **Selective opportunity** (avg score 10–20) | Good candidates exist but require some prep work. Evaluate the top 3 workloads and plan a Phase 2 scope. |
| **Early-stage** (avg score < 10) | Migration is not the near-term move. Address complexity drivers (UDFs, compliance) or wait for platform pain to increase. |

The exact thresholds are set per engagement based on your platform and workload profile.

## The priority breakdown

A table shows your workloads grouped into the three priority buckets:

| Bucket | Count | Average Score | Average Savings |
| --- | --- | --- | --- |
| Priority 1 | N | XX | XX% |
| Evaluate | N | XX | XX% |
| Hold | N | XX | XX% |

The ratio of Priority 1 to Evaluate tells you the shape of the migration program. A high Priority 1 count means a quick PoC and fast value realization. A high Evaluate count means the program needs a remediation phase before migration — still worth doing, just a longer runway.

## The top PoC candidates

The assessment recommends three workloads to migrate first, ranked by adjusted Opportunity Score. For each:

- **Name and platform.** What the workload is and where it lives today.
- **Score and priority.** The opportunity score and priority bucket.
- **Estimated monthly savings.** The dollar delta for this workload alone.
- **Migration effort.** Low / Medium / High, with a one-line explanation.
- **Workload type.** The fit category (analytics, point lookup, app backend, etc.).

These three are the PoC scope. A two-week Blueprint PoC sprint will migrate one end-to-end, validate the cost savings, and give your team the pattern to migrate the others.

## The cost-benefit table

A side-by-side comparison of your current platform costs vs. the Lakebase projection:

| Item | Current Platform | Lakebase (projected) | Delta |
| --- | --- | --- | --- |
| Compute | $X/mo | $X/mo | -XX% |
| Storage | $X/mo | $X/mo | -XX% |
| Scaling overhead | $X/mo | $0 (serverless) | -100% |
| Total | $X/mo | $X/mo | -XX% |

**Confidence level** (High / Medium / Low) is shown next to the projection. High means 6+ months of query history with a consistent workload pattern. Low means sparse history; treat projections as directional.

## The savings payback

Most migrations pay back any PoC investment within the first month of production traffic on Lakebase. The executive summary includes a simple payback table:

| Phase | Estimated Cost | Monthly Savings | Payback Period |
| --- | --- | --- | --- |
| PoC (2 weeks) | $0–$25K | $X/mo (Phase 1 only) | < 1 month |
| Phase 2 migration | $X | $X/mo (full estate) | 2–4 months |

If the payback period is more than 6 months, the complexity scores are likely high and the program should start with a refactoring sprint before full migration.

## What to do with this page

After your first read:

1. **Confirm the savings are material.** If estimated annual savings are below $100K, the migration may not justify the program overhead. Ask your account executive for a sensitivity analysis with your actual negotiated Lakebase rates.
2. **Decide on a PoC.** If Priority 1 count ≥ 3 and confidence is High or Medium, authorize a 2-week PoC. Blueprint can begin within 1 week of kickoff authorization.
3. **Nominate a tech lead.** The PoC needs one owner on your team who can provision access, review query results, and sign off on validation. Typically a senior data engineer or platform architect.
4. **Set the Phase 2 decision date.** Most customers decide on Phase 2 within 2 weeks of PoC completion. Block the calendar now.

Hand the [data owner page](data-owner.md) to your domain leads for workload-level triage and the [engineer page](engineer.md) to the technical team who will execute the migration.
