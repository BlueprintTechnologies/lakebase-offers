# Migration Playbooks

Step-by-step guides for migrating each workload type. Pick the playbook that matches the classification shown in your assessment report.

## Choose your playbook

| Classification (from your scorecard) | Playbook | Effort |
| --- | --- | --- |
| Analytics → Keep in Delta | [Analytics to Delta](analytics-to-delta.md) | Low — 1–2 weeks |
| Point Lookups → Migrate + Cache | [Point Lookups + Cache](point-lookups.md) | Medium — 2–4 weeks |
| App Backends → Migrate to Lakebase | [App Backends](app-backends.md) | Medium — 3–6 weeks |
| Agent State → Migrate to Lakebase | [Agent State & Feature Serving](agent-state.md) | Medium — 2–4 weeks |
| Feature Serving → Migrate to Lakebase | [Agent State & Feature Serving](agent-state.md) | Medium — 2–4 weeks |
| Real-time Join/Agg → Lakebase + Cache | [Real-time Aggregations](realtime-aggs.md) | Medium — 4–6 weeks |
| Heavy ETL/UDF → Refactor First | [Heavy ETL — Refactor First](heavy-etl.md) | High — 8–12 weeks |

## Before you start any playbook

Complete the relevant [Trust Foundations](../trust-foundations/index.md) for this workload:

- [ ] [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) — always required
- [ ] [Access Control Review](../trust-foundations/access-control.md) — always required
- [ ] [Data Inventory & Schema Docs](../trust-foundations/data-inventory.md) — required if schema is undocumented
- [ ] [Compliance & Governance](../trust-foundations/compliance.md) — required if PII or compliance flags exist
- [ ] [Data Quality Baseline](../trust-foundations/data-quality.md) — required for data-critical or high-traffic workloads

## The per-workload migration checklist

Every playbook uses this base checklist:

```
Pre-migration:
[ ] SQL compatibility check complete; all High flags resolved
[ ] Access control replicated in Unity Catalog
[ ] Compliance review complete (if PII/regulated)
[ ] Data quality baseline captured on source

Migration:
[ ] Schema created in Unity Catalog
[ ] Data loaded (initial full load or incremental)
[ ] Row counts validated (must match source)
[ ] Aggregation correctness validated (spot check 5 key queries)
[ ] P95 latency validated against SLA target

Go-live:
[ ] Connection strings updated in downstream consumers
[ ] Source platform workload placed in read-only mode
[ ] 72-hour monitoring window started
[ ] Error rate < 0.1% for 72 hours ✓
[ ] Business owner sign-off ✓
[ ] Source workload decommissioned
```

Adapt the checklist for your workload type. Each playbook adds the workload-specific steps to this base.
