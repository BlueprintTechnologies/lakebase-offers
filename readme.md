# Blueprint Lakebase Offers

Blueprint's portfolio of $0 Lakebase readiness assessments and the accelerators that power them. Each offer is a fixed-scope, time-bound engagement designed to unlock immediate ROI for customers adopting Databricks Lakebase, aligned with the Databricks SQL migration playbook.

> **Customer playbook (public):** [The Lakebase Migration Playbook](#) — the customer-facing reference for interpreting readiness results, planning migration phases, and optimizing performance. Share this URL with customers and account stakeholders.

## Portfolio

| Offer | Duration | Core Accelerator | Status |
| --- | --- | --- | --- |
| [Lakebase Readiness in 2–3 Weeks](lakebase-assess/) | 2–3 weeks | Lakebase Readiness Assessor | Production |
| [Lakebase PoC Accelerator](docs/poc-framework.md) | 2 weeks | Migration Framework + Playbook | In development |

## Positioning

Each offer is designed to be:

- Zero cost for the initial engagement, to remove procurement friction and drive velocity.
- Time-bound and outcome-oriented, with a defined set of artifacts delivered to the customer.
- Backed by a reusable accelerator that carries the majority of delivery effort, enabling Blueprint to deliver profitably even at zero cost.
- A credible on-ramp to paid follow-on work (PoC, migration execution, optimization, training).

## Repository Layout

```
lakebase-assess/              Core assessor tool (CLI, Python package)
├── src/                      Assessment engine: connectors, scoring, billing, outputs
├── tests/                    Unit & integration tests
├── pricing_maps/             YAML configs for platform pricing
├── templates/                Report templates (PDF, HTML, JSON)
└── pyproject.toml            Dependencies & configuration

docs/                         Customer-facing playbook (published to GitHub Pages)
├── index.md                  Start here: roles-based navigation
├── getting-started/          First-time setup & interpretation guide
├── scorecard-anatomy/        What each scoring dimension means
├── migration-playbooks/      Step-by-step guides for each workload type
├── trust-foundations/        Data governance & preparation checklist
└── faq.md                    Common questions

reference/                    Databricks SQL & platform resources
```

This project is **not open-source**. It is released under the **Blueprint Business Source License (BSL) 1.1**, which allows organizations to use the code internally for evaluation and migration assessment, but **prohibits commercial use, resale, hosting as a service, or white-labeling**.

---

## ✨ What This Accelerator Includes

### The Assessor (lakebase-assess)
A **read-only CLI tool** that profiles your legacy platform and generates a comprehensive readiness scorecard:

- **Platform Connectors** → Query history and metadata collection for Snowflake, BigQuery, Redshift, Oracle, Teradata, Vertica, Azure Synapse, on-prem systems
- **Opportunity Scoring** → Quantifies readiness (0–100) and prioritizes workloads for migration
- **Cost Modeling** → Estimates annual savings by workload and platform
- **Workload Classification** → Maps workloads to seven Lakebase fit categories (analytics, point lookups, agent state, app backends, feature serving, heavy ETL, real-time aggregations)
- **Report Generation** → PDF executive summary, JSON payload, CSV exports, HTML dashboard

### The Outputs (Customer-Facing)
- **Executive Scorecard** → One-page readout: top findings, estimated ROI, top 3 PoC candidates
- **Detailed Assessor Report** → Per-workload scores, blockers, recommendations, effort estimates
- **Cost-Benefit Analysis** → Monthly & annual savings projections vs. current platform
- **Migration Roadmap** → Phased approach with effort estimates and risk flags
- **PoC Proposal** → Scope and timeline for first-phase migration validation

### The Playbooks (Documentation)
- Customer-facing interpretation guides for each role (executive, data owner, engineer)
- Migration playbooks for each workload type
- Trust foundations: data governance, schema prep, testing checklists
- FAQ and troubleshooting

---

## 🏃 Quick Start

### For Blueprint (Running an Assessment)

```bash
# Install the assessor
pip install -e lakebase-assess/

# Run against a customer's Snowflake environment
lakebase-assess run \
  --platform snowflake \
  --config ./my-customer-config.yaml \
  --output-dir ./assessment-output \
  --anonymize \
  --threshold 10

# Outputs: report.pdf, results.json, executive_summary.html, blockers.csv
```

See [ACCELERATOR.md](./ACCELERATOR.md) for full setup and running instructions.

### For Customers (Reading Your Assessment)

1. **Get your executive summary:** Open `executive_summary.html` or the PDF
2. **Understand your score:** Each workload is scored 0–100. Scores ≥25 are PoC candidates.
3. **Pick your first 3:** The report highlights Priority 1 workloads (easiest, highest ROI)
4. **Plan your roadmap:** Use the recommended phasing and effort estimates to build your migration plan
5. **Read the playbook:** See [docs/index.md](./docs/index.md) for role-based guides

---

## 📊 Example Output

After running an assessment, you'll see:

**Executive Summary:**
```
Platform: Snowflake
Workloads Assessed: 150
Priority 1 (Ready Now): 42 workloads, avg. score 72
Evaluate (Needs Prep): 68 workloads, avg. score 16
Hold (Not Yet Ready): 40 workloads, avg. score 6

Estimated Annual Savings: $2.8M (42% of current spend)
Recommended PoC Timeline: 2–3 weeks
Recommended Phase 2 Timeline: 8–12 weeks
```

**Workload Example (Analytics Dashboard):**
```
Name: customer_revenue_analytics
Platform: Snowflake
Type: Analytics (Read-heavy aggregations)
Opportunity Score: 87 (Priority 1)
Pain: 8/10 (peak concurrency issues)
Business Impact: 9/10 (CFO dashboard, daily use)
Complexity: 2/10 (Standard SQL, no UDFs)

Estimated Monthly Savings: $18K ($216K/year)
Migration Effort: 1–2 weeks
Recommended Actions:
  1. Migrate schemas to Delta Lake (2 days)
  2. Rewrite 3 aggregation queries (3 days)
  3. Validate results against current platform (2 days)
  4. Cutover & monitor (1 day)
```

---

## 🔒 License Summary (BSL 1.1)

You may:
- Clone, modify, and use this repository internally  
- Use it for Lakebase migration evaluation, planning, and proof-of-concept work  

You may **not**:
- Sell, resell, or monetize this software  
- Offer it as a hosted service  
- Incorporate it into a commercial product  
- White‑label or rebrand it as your own consulting accelerator  
- Use it to compete with Blueprint Technologies’ commercial offerings  

For full details, see the [`LICENSE`](./LICENSE) file.

---

## 🚀 What Happens Next

**If you're a Blueprint customer:** Your assessment results come with a proposal for **Lakebase PoC (Free+ support)** — a 2-week sprint where we migrate your top Priority 1 workload end-to-end. You see real cost numbers, your team learns the migration patterns, and you control whether to execute Phase 2 migrations in-house or with Blueprint support.

**If you're exploring Lakebase:** Download the code, run a self-service assessment against your sandbox environment, and see if migration makes sense for your use cases. Public docs are in `./docs/`.

---

## 📖 See Also

- **[ACCELERATOR.md](./ACCELERATOR.md)** — Full setup guide, running the assessor, customizing configs
- **[docs/index.md](./docs/index.md)** — Customer-facing playbook (start here to understand your assessment results)
- **[reference/](./reference/)** — Databricks SQL and migration resources
- **Databricks Lakebase Docs:** [docs.databricks.com](https://docs.databricks.com/en/sql/index.html)
- **Databricks SQL Migration Guide:** [Migrating from Snowflake/Redshift/BigQuery to Databricks SQL](https://docs.databricks.com/en/sql/migration/index.html)

---

## 🏢 About Blueprint Technologies

Blueprint Technologies is a modern data and AI consultancy specializing in:
- **Databricks Lakehouse & Lakebase** → Platform consolidation, cost reduction, SQL migrations
- **Generative AI & Agents** → Building AI-powered data products with Databricks Genie and custom agents
- **Cloud-scale data engineering** → Scalable ELT, real-time pipelines, governance
- **AI/ML platforms** → Feature stores, model serving, MLOps on Databricks

We build *accelerators* like this one to make migrations faster, less risky, and more profitable for both customers and Blueprint.

Learn more at: https://bpcs.com

