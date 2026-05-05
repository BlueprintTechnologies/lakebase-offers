# Workload Classifications

Every assessed workload is classified into one of seven fit categories based on its query patterns, data access needs, and write behavior. The classification tells you which migration playbook to follow.

## The seven categories

| Classification | Lakebase Fit | Migration Effort | Typical Score Range |
| --- | --- | --- | --- |
| [Analytics → Keep in Delta](#analytics--keep-in-delta) | Excellent | Low (1–2 weeks) | 50–100 |
| [Point Lookups → Migrate + Cache](#point-lookups--migrate--cache) | Excellent | Medium (2–4 weeks) | 40–90 |
| [Agent State → Migrate to Lakebase](#agent-state--migrate-to-lakebase) | Excellent | Medium (2–4 weeks) | 30–80 |
| [App Backends → Migrate to Lakebase](#app-backends--migrate-to-lakebase) | Good | Medium (3–6 weeks) | 25–70 |
| [Feature Serving → Migrate to Lakebase](#feature-serving--migrate-to-lakebase) | Excellent | Medium (2–4 weeks) | 30–80 |
| [Real-time Join/Agg → Lakebase + Cache](#real-time-joinagg--lakebase--cache) | Good | Medium (4–6 weeks) | 20–60 |
| [Heavy ETL/UDF → Refactor First](#heavy-etludf--refactor-first) | Risky | High (8–12 weeks) | 5–30 |

---

## Analytics → Keep in Delta

**What it is:** Read-heavy SQL — aggregations, rollups, filters, joins across fact and dimension tables. Queries run on schedules (hourly, daily) or are user-driven from dashboards and BI tools.

**How the assessor detects it:** High read/write ratio (> 95% SELECT). Queries are aggregations or joins. No UDF calls. Standard SQL dialect.

**Why Lakebase excels:** Lakebase SQL is a drop-in replacement for Snowflake and BigQuery SQL on analytics workloads. Delta Lake's columnar format + Lakebase query optimization produces 2–5x faster scans with 40–80% lower compute cost.

**Migration path:** Move schemas to Delta, validate row counts, update connection strings. Typically 1–2 weeks.

**Playbook:** [Analytics to Delta](../migration-playbooks/analytics-to-delta.md)

---

## Point Lookups → Migrate + Cache

**What it is:** Sub-second single-row or small-set lookups. "Give me the price for product_id=12345." High concurrency (1000s req/sec) from app backends or APIs.

**How the assessor detects it:** Queries with single-column WHERE equality filters. Low scan volume (< 1000 rows). High query frequency. Often called from application service accounts.

**Why Lakebase excels:** Lakebase SQL with caching delivers < 100ms P95 latency at high concurrency. Zero-copy sharing means multiple apps access the same data without duplication.

**Migration path:** Configure Lakebase caching for the hot access pattern. Update application connection strings. Load test before cutover.

**Playbook:** [Point Lookups + Cache](../migration-playbooks/point-lookups.md)

---

## Agent State → Migrate to Lakebase

**What it is:** Transactional state for AI/ML agents — embeddings, conversation history, per-user context. Frequent small writes (1–10 KB), sub-second reads.

**How the assessor detects it:** Small row sizes. High write frequency with UPSERT/MERGE patterns. Queries filter on session or user ID. Often from AI pipeline service accounts.

**Why Lakebase excels:** ACID MERGE + Delta Lake = reliable agent state with full audit trail. Unity Catalog governance means agents safely access shared feature stores. Delta time travel enables agent state replay and debugging.

**Migration path:** Design UPSERT schema, configure MERGE-on-read, test write throughput. Add caching for sub-100ms read path.

**Playbook:** [Agent State & Feature Serving](../migration-playbooks/agent-state.md)

---

## App Backends → Migrate to Lakebase

**What it is:** Operational data for user-facing applications — user profiles, orders, inventory. Mix of reads and writes. Moderate concurrency (100–1000 concurrent users). Transactional semantics expected.

**How the assessor detects it:** Balanced read/write ratio. Queries filter on primary key. Multiple service accounts from different applications. SLA sensitivity in query latency.

**Why Lakebase excels:** Full ACID transactions + Delta governance. Serverless compute = no DB ops, auto-scaling. Zero-copy sharing: backend systems share data without replication overhead.

**Migration path:** Schema migration, ACID validation, connection pooling design, app connection string updates. Load test for concurrent write correctness.

**Playbook:** [App Backends](../migration-playbooks/app-backends.md)

---

## Feature Serving → Migrate to Lakebase

**What it is:** Pre-computed ML features for model training (batch, 100K features/run) and model serving (single-row, sub-second at inference time).

**How the assessor detects it:** Wide tables (100+ columns). Mixed batch reads (training) and point reads (inference). Service accounts from ML pipelines. Queries that look like feature vector fetches.

**Why Lakebase excels:** Lakebase + Delta = unified feature retrieval for training and serving. Delta versioning allows reproducing models with historical features. 80% cheaper than dedicated feature platforms (Feast, Tecton).

**Migration path:** Adapt feature computation pipeline to write to Delta. Configure serving API to query Lakebase. Validate online/offline parity.

**Playbook:** [Agent State & Feature Serving](../migration-playbooks/agent-state.md)

---

## Real-time Join/Agg → Lakebase + Cache

**What it is:** Low-latency aggregations across multiple tables — customer lifetime value, real-time inventory levels, event aggregation. Updates every seconds to minutes via streaming or micro-batch.

**How the assessor detects it:** Aggregation queries with GROUP BY. High query frequency. Evidence of streaming writes (Kafka, Kinesis) to source tables. Latency SLA < 1 second.

**Why Lakebase excels:** Lakebase + Delta incremental aggregations + an optional external cache (Redis, Memcached) delivers sub-50ms P95 at a fraction of the cost of Druid, Pinot, or custom streaming systems.

**Migration path:** Configure Delta streaming tables for incremental aggregation. Add caching layer for the sub-second serving path. Validate late-arriving data behavior.

**Playbook:** [Real-time Aggregations](../migration-playbooks/realtime-aggs.md)

---

## Heavy ETL/UDF → Refactor First

**What it is:** Complex transformations with heavy UDFs, custom logic, stored procedures, or machine learning embedded in SQL. Technologies: Oracle PL/SQL, T-SQL stored procedures, R/Python UDFs.

**How the assessor detects it:** High UDF call count per query. Stored procedure dependencies. Proprietary SQL dialect usage. Long query runtimes (> 30 minutes). Low read/write ratio (this workload is primarily compute, not data serving).

**Why Lakebase is risky without prep:** UDF syntax requires rewriting. Custom binary formats may not map to Delta. Embedded ML (Oracle Data Mining) has no direct equivalent.

**Migration path:** Decompose into smaller, refactorable units. Rewrite UDFs as Python + Spark. Validate data correctness with dual-run. Then migrate.

**Playbook:** [Heavy ETL — Refactor First](../migration-playbooks/heavy-etl.md)

---

## How classification interacts with score

The classification does not directly change the Opportunity Score — it is a label that directs you to the right playbook. However, classification influences the **Complexity** dimension:

- Analytics, Point Lookups, and Feature Serving workloads tend to have lower Complexity scores (1–4), pushing their Opportunity Scores higher.
- Heavy ETL workloads tend to have Complexity 7–10, pulling their scores into the Evaluate or Hold range.

If a workload is classified as Heavy ETL but the data owner believes it should be Analytics, flag it to your account executive. The assessor may be detecting UDF dependencies that are not actually called in production, which inflates complexity.
