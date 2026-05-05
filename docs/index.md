# The Lakebase Migration Playbook

Databricks Lakebase is a powerful, cost-efficient SQL engine for analytics and operational data. This playbook is the practical guide to understanding your readiness assessment, planning migration phases, and optimizing performance.

## What This Playbook Is For

Three things, in this order:

1. **See your readiness assessment.** An automatically-generated scorecard that tells you whether your data and workloads are in shape for Lakebase. [Reading Your Assessment](#) walks the dashboard.
2. **Understand your scores.** What does a score of 85 mean? Why is this workload "Priority 1" and that one "Hold"? [Anatomy of Your Scorecard](#) explains the five dimensions.
3. **Build your migration plan.** [Migration Playbooks](#) is step-by-step guidance for each workload type. [Trust Foundations](#) prepares your data. [Path to Scale](#) is your 30/60/90 roadmap.

## Pick Your Path

| If you are... | Start here |
| --- | --- |
| About to present your assessment to leadership | [For Executives](#for-executives) |
| Reviewing data governance and architecture | [For Data Owners](#for-data-owners) |
| Planning the technical migration | [For Engineers](#for-engineers) |
| Evaluating cost-benefit | [Cost & Performance](#cost--performance) |
| New to Databricks | [Databricks 101](#databricks-101) |
| Diagnosing a problem | [Troubleshooting](#troubleshooting) |

---

## For Executives

**Goal:** Understand the business case and timeline.

**Your Scorecard Page:**
- **Top-line metrics:** Overall readiness score, estimated annual savings, priority workloads
- **Go-live readiness:** A simple "On Track / Attention / Blocker" checklist
- **Readiness-by-domain:** Which parts of your data infrastructure are ready
- **Path forward:** Phased roadmap with effort estimates

**Key Questions You'll Answer:**
- How much can we save? (Typical: 30–60% on SQL platform costs)
- How long will migration take? (Typical: 4–6 months for full estate)
- What's the risk? (Lakebase SQL is 99%+ compatible with legacy platforms)
- When do we start seeing value? (Within 2–3 weeks of PoC kickoff)

👉 [Executive Guide](executives.md) — One-page interpretation of your scorecard

---

## For Data Owners

**Goal:** Prioritize remediation and plan domain-by-domain migration.

**Your Scorecard Page:**
- **Readiness funnel:** What % of your tables clear each readiness gate
- **Usage vs. readiness:** Which of your most-used tables need prep work
- **Blocker summary:** PII masking, schema complexity, compliance requirements
- **Domain trends:** How governance coverage changes over time

**Key Questions You'll Answer:**
- Which of my tables are ready for Lakebase today?
- Which ones need prep work, and how much effort?
- What's the PII/compliance plan?
- Who owns each workload's migration?

👉 [Data Owner Guide](data-owners.md) — Deep-dive on readiness dimensions and remediation

---

## For Engineers

**Goal:** Execute migration with the right patterns and tooling.

**Your Scorecard Page:**
- **Full table explorer:** Per-table scores, detailed blockers, remediation suggestions
- **Dimension drill-down:** Why did this table score 15? What specifically needs fixing?
- **Remediation backlog:** Copy-paste-ready SQL suggestions for blockers
- **Performance baseline:** What queries ran at on legacy platform; your target on Lakebase

**Key Questions You'll Answer:**
- What's the easiest table to migrate first? (High score, small size, simple schema)
- What do I need to change in my ETL? (Data types, functions, access patterns)
- How do I validate the migration? (Data matching, query result validation, performance testing)
- Where's the gotchas? (Null handling, type coercion, reserved keywords)

👉 [Engineer Guide](engineers.md) — Migration patterns, testing playbooks, optimization

---

## Reading Your Assessment

Your scorecard has **two pages: Executive and Technical.**

### Understanding Opportunity Scores (0–100)

Your assessment scored each workload on **three dimensions:**

1. **Pain (1–10):** How much does this workload hurt right now?
   - Slow queries, scaling issues, frequent failures
2. **Business Impact (1–10):** How important is this workload?
   - Revenue-critical, CFO dashboard, core operations, or ad-hoc?
3. **Complexity (1–10):** How hard is it to migrate?
   - Simple SQL, or heavy UDFs and legacy syntax?

The **Opportunity Score** is: `((Pain × Impact) / Complexity) × 10`

Then adjusted for **Estimated Savings,** creating your final priority.

### Priority Buckets

| Score | Label | Meaning |
|-------|-------|---------|
| **≥ 25** | **Priority 1** | Migrate now. High confidence, low effort, strong ROI. |
| **10–24** | **Evaluate** | Worth migrating, but needs prep work first. Plan for Phase 2. |
| **< 10** | **Hold** | Not ready yet. Optimize current platform or revisit in 6–12 months. |

---

## Cost & Performance

### Expected Savings

**Typical range: 30–60% cost reduction** on SQL platform costs.

| Workload Type | Cost Savings | Performance Gain |
|---|---|---|
| Analytics (SELECT-heavy) | 50–80% | 2–5x faster |
| Point lookups (cached) | 70–85% | 10–50x faster (sub-second) |
| App backends | 40–60% | 1.5–3x faster, simpler ops |
| Real-time aggregations | 60–75% | 3–10x faster, lower latency |
| Heavy ETL (optimized) | 20–40% | 2–4x faster, simpler code |

### Monthly Cost Estimate

Your assessment includes a **cost comparison table** showing:

```
Platform          Monthly Cost    Annual Cost    Your Usage Pattern
Snowflake         $18,500         $222,000       (based on your actual queries)
BigQuery          $14,200         $170,400
Redshift          $16,700         $200,400
Lakebase (est.)   $8,200          $98,400

Estimated Savings: $9,900–10,300/month ($119–124K/year)
Payback Period:    Immediate (Lakebase is cheaper from day 1)
```

---

## Anatomy of Your Scorecard

The assessment scores each workload on **five dimensions:**

1. **Metadata Completeness** — Does Lakebase understand your data?
   - Table & column comments, data types, partitioning
2. **Semantic Relationships** — Can Lakebase join your tables?
   - Primary/foreign keys, lineage, data contracts
3. **Governance Posture** — Is your data secure & auditable?
   - RBAC, encryption, PII masking, data lineage
4. **Usage Signals** — Do your users actually rely on this data?
   - Query frequency, users, dependencies
5. **Critical Blockers** — Are there show-stoppers?
   - Compliance gating, unsupported functions, custom serialization

👉 [Detailed Anatomy](scorecard-anatomy/) — One page per dimension, plain-language explanation

---

## Migration Playbooks

Each workload type has a different migration path.

### Playbook Selection

| Workload Type | Best For | Migration Effort | Key Risks |
|---|---|---|---|
| **Analytics → Keep in Delta** | Reports, dashboards, OLAP | Low (1–2 weeks) | Complex window functions |
| **Point Lookups + Cache** | Real-time lookups, customer master data | Medium (2–4 weeks) | Cache freshness, consistency |
| **Agent State (Feature Store)** | AI/ML agent context, embeddings | Medium (2–4 weeks) | Vector similarity search, write throughput |
| **App Backends** | Transactional OLTP, user-facing data | Medium (3–6 weeks) | Distributed transaction consistency |
| **Feature Serving** | ML feature computation & retrieval | Medium (2–4 weeks) | Online/offline feature skew |
| **Heavy ETL** (⚠️ Risky) | Complex transformations, UDF-heavy | High (8–12 weeks) | Code rewrite, testing effort |
| **Real-time Agg + Cache** | Live metrics, streaming aggregations | Medium (4–6 weeks) | Late-arriving data, consistency |

👉 [Full Playbooks](migration-playbooks/) — Step-by-step for each pattern

---

## Trust Foundations

Before you migrate, **prepare your data** for governance and performance.

### Five Foundations

1. **Add table comments** — Lakebase uses metadata to power recommendations & AI/BI
2. **Declare primary/foreign keys** — Helps Lakebase join correctly and enforce integrity
3. **Tag your domains** — Organize data by owner, SLA, compliance level
4. **Add column-level masking** — Protect PII automatically (Unity Catalog)
5. **Register certified functions** — Mark trusted UDFs for AI/BI querying

👉 [Trust Foundations Playbooks](trust-foundations/) — Checklist + SQL for each

---

## Path to Scale

After your first workload migrates, **scale to the rest of your estate** with these playbooks.

### 30/60/90 Day Roadmap

| Phase | Milestones | Output |
|-------|-----------|--------|
| **Days 1–30 (Stabilize)** | First workload in production, team trained, patterns locked | 1 production workload, runbook, team certified |
| **Days 31–60 (Expand)** | 3–5 workloads migrated in parallel, governance in place | Phase 1 complete (analytics + one point-lookup) |
| **Days 61–90 (Accelerate)** | Remaining workloads in flight, team self-sufficient | Full estate migrated or roadmap clear for Phase 2 |

👉 [Path to Scale](path-to-scale.md) — Templates for sprints, stakeholder comms, success metrics

---

## Databricks 101

New to Databricks? Start here.

### Five Concepts

1. **Unity Catalog** — Unified governance across all your data (tables, files, models, notebooks)
2. **Lakebase SQL** — A SQL engine on Delta Lake with warehouse performance
3. **Delta Lake** — Open data format (parquet + transaction log) that powers analytics & AI
4. **Databricks Workspace** — Your IDE for SQL, Python, R, dashboards (think: Jupyter + Git + IDE)
5. **AI/BI** — Databricks' built-in BI tool (ask questions in plain English, get charts)

👉 [Databricks Vocabulary](databricks-101.md) — Glossary of 20 key terms

---

## Troubleshooting

### "My data looks wrong after migration"

1. Check **row counts**: Do source and target match?
2. Check **nullability**: Did `NULL` values change?
3. Check **type coercion**: Did numeric strings become numbers?
4. Check **distinctness**: Are duplicate rows expected?

👉 [Data Validation Checklist](troubleshooting.md#data-validation)

### "Queries are slower than expected"

1. Is the query **hitting cold storage** (first run)?
2. Is **join selectivity low** (scanning 90% of table)?
3. Are there **missing statistics** on partition columns?

👉 [Performance Tuning](troubleshooting.md#performance-tuning)

### "Users are seeing different results"

1. Check **query timestamps** (did time-based filters change?)
2. Check **user-specific ACLs** (is user seeing all rows?)
3. Check **union/join logic** (did schema change?)

👉 [Result Validation](troubleshooting.md#result-validation)

---

## FAQ

**Q: Do we have to migrate everything at once?**
A: No. Migrate 3–5 Priority 1 workloads first (PoC phase), validate, then migrate the rest in phases.

**Q: How long does a full migration take?**
A: For a typical enterprise with 50 workloads, plan 4–6 months. Larger estates: 6–12 months. Smaller teams may go faster.

**Q: Can we keep some workloads on the legacy platform?**
A: Yes. Many customers run a hybrid: Lakebase for analytics & app backends, Snowflake for specialized BI tools (rare).

**Q: What if we have compliance requirements we're worried about?**
A: Most compliance concerns (encryption, audit trails, masking, retention) are handled by Unity Catalog. See [Trust Foundations](trust-foundations/).

**Q: What about our existing dashboards / BI tools?**
A: Lakebase works with Tableau, Looker, Power BI, Excel, and any tool that speaks SQL. Zero BI tool changes needed.

---

## Reference

- **[Databricks Lakebase Docs](https://docs.databricks.com/en/sql/index.html)**
- **[Databricks SQL Migration Guide](https://docs.databricks.com/en/sql/migration/index.html)**
- **[Unity Catalog Security & Governance](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)**
- **[Lakebase Performance Tuning](https://docs.databricks.com/en/sql/query-editor-optimization.html)**

---

## Next Steps

1. **Review your assessment** — Open the PDF or HTML report
2. **Pick your first 3 workloads** — Start with Priority 1 scores (≥25)
3. **Read the relevant playbook** — Pick the pattern that fits (analytics, lookups, etc.)
4. **Validate your data** — Use the Trust Foundations checklist
5. **Contact Blueprint** — Ready for a PoC? We can run one in 2 weeks

**Questions?** Email [support@bpcs.com](mailto:support@bpcs.com) or check the [FAQ](faq.md).

