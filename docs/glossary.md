# Glossary

Key terms used throughout the Lakebase assessment and migration documentation.

## A

**ACID transactions**
Atomicity, Consistency, Isolation, Durability — the four properties that guarantee database transactions are processed reliably. Delta Lake provides ACID semantics at scale, which is what makes Lakebase suitable for transactional app backends.

**Auto-compaction**
A Delta Lake feature (`delta.autoOptimize.autoCompact = 'true'`) that automatically merges small files in the background. Reduces the need for manually-scheduled OPTIMIZE jobs on frequently-written tables.

## B

**Bloom filter**
A probabilistic data structure that lets Delta Lake skip files that definitely don't contain a queried value. Enable on high-cardinality lookup keys (like `customer_id` or `order_id`) to dramatically improve point lookup performance. Configure with `delta.bloomFilter.<column>.enabled = 'true'`.

**Blueprint BSL 1.1**
The source-available license that governs the `lakebase-assess` accelerator. Permits use for internal assessment, consulting, and CoAA delivery. Prohibits resale as SaaS, white-labeling, or redistribution without attribution.

**BPCS (Blueprint Professional Cloud Services)**
Blueprint's professional services arm that delivers the Lakebase Assessment and migration engagements.

## C

**Catalog**
The top-level namespace in Unity Catalog's three-level hierarchy: `catalog.schema.table`. Typically named by environment (`prod`, `dev`, `staging`).

**CDC (Change Data Feed / Change Data Capture)**
The ability to read a stream of INSERT, UPDATE, and DELETE operations from a Delta table. Enable with `delta.enableChangeDataFeed = 'true'`. Used for real-time sync from source platforms and for replacing database triggers.

**Cluster (Databricks)**
A set of compute nodes running Apache Spark. Not the same as a SQL Warehouse — clusters are used for ETL, ML, and streaming jobs. SQL Warehouses have their own managed compute.

**Complexity (scoring dimension)**
One of the three scoring dimensions in the Lakebase Opportunity Score. Measures how hard it is to migrate the workload: SQL compatibility flags, UDF usage, stored procedure count, binary formats. Higher complexity = lower score = lower migration ROI.

**Connection pool**
A cache of database connections maintained so that applications don't need to create a new connection for each query. Recommended for app backends using Lakebase: use HikariCP (Java) or a custom pool (Python).

**CoAA (Customer-Owned Accelerated Assessment)**
The full, paid engagement model where Blueprint delivers a comprehensive assessment plus migration execution. Contrast with the Free and Free+ tiers.

## D

**Data Quality Baseline**
A Trust Foundation that captures statistical summaries (row counts, NULL rates, value distributions, numeric ranges) of the source data before migration. Used to validate that the migrated data matches the source.

**DBU (Databricks Unit)**
The billing unit for Databricks compute. One DBU is roughly equivalent to 4 vCPUs of processing capacity, standardized across instance types. SQL Warehouse pricing is expressed in DBU-hours.

**Delta Lake**
The open-source storage format that underlies all Lakebase tables. Adds ACID transactions, schema enforcement, time travel, and scalable metadata to Parquet files stored in cloud object storage.

**Delta Live Tables (DLT)**
Databricks' declarative pipeline framework. Define transformations using the `@dlt.table` decorator; DLT handles orchestration, error handling, and data quality checks.

## E

**Evaluate (priority bucket)**
Workloads with a Lakebase Opportunity Score of 10–24. Worth migrating after Priority 1 workloads are complete, but with a more careful cost/benefit review. See [Scorecard Anatomy](scorecard-anatomy/index.md).

## F

**Feature Store**
A managed store of pre-computed ML features, enabling consistent feature values between training and serving. Delta tables in Unity Catalog serve as the feature store in Lakebase; register them with MLflow Feature Store client.

**Foreign key**
In Delta Lake, foreign key constraints are informational (declared but not enforced on write). The application is responsible for referential integrity. Declare with `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`.

## H

**Hold (priority bucket)**
Workloads with a Lakebase Opportunity Score below 10. Migration cost exceeds near-term benefit; defer until Priority 1 and Evaluate workloads are complete, or until the workload's complexity decreases.

**HTTP path**
The URL path that identifies a specific SQL Warehouse in a Databricks workspace. Format: `/sql/1.0/warehouses/<warehouse-id>`. Required in all JDBC/ODBC connection strings and SDK connections.

## J

**JDBC**
Java Database Connectivity — the standard API for database connections. Databricks provides a JDBC driver for SQL Warehouses. Download from the workspace UI: SQL Warehouses → Connection details → Download JDBC driver.

## L

**Lakebase**
Databricks' branded SQL query experience: a SQL Warehouse (compute) connected to Delta Lake tables (storage) managed by Unity Catalog (governance). "Lakebase" emphasizes the OLTP + analytics convergence use case.

**Lakebase Opportunity Score**
Blueprint's formula for ranking migration ROI: `Score = ((Pain × Business_Impact) / Complexity) × 10`. Higher scores indicate better migration candidates. Adjusted score multiplies by `(1 + savings_pct/100)` when cost savings are known.

**Liquid Clustering**
A Delta Lake optimization that automatically co-locates related data without requiring static partition columns. Preferred over `PARTITION BY` for OLTP tables and point lookup workloads. Configure with `CLUSTER BY (column_name)`.

## M

**Materialized view**
In Delta Lake, pre-computed aggregations stored as Delta tables and refreshed on a schedule or via streaming. Not a native Delta concept (Delta doesn't have built-in materialized views), but achieved via scheduled notebooks or DLT pipelines.

**Metastore**
The Unity Catalog metastore is the top-level governance object that manages catalogs, schemas, and access policies across a Databricks account. One metastore per cloud region.

**MERGE**
The SQL statement for upsert operations in Delta Lake. Combines INSERT and UPDATE in a single atomic operation. Replaces patterns like "INSERT or UPDATE" or "UPSERT" from other platforms.

## O

**OPTIMIZE**
The Delta Lake command that compacts small files and optionally co-locates data (via `ZORDER BY`). Run periodically on tables with frequent writes to maintain read performance.

## P

**Pain (scoring dimension)**
One of the three scoring dimensions. Measures how much the workload is hurting the business: latency issues, cost overruns, availability problems, user complaints. Higher pain = higher score = stronger migration case.

**PAT (Personal Access Token)**
An authentication token for Databricks APIs and SQL connections. Generated in the workspace UI: Settings → Developer → Access Tokens. Use service principal tokens for production workloads.

**Photon**
Databricks' vectorized query engine that accelerates SQL query execution. Enabled automatically on SQL Warehouses. Particularly effective for large aggregations and joins.

**Priority 1 (priority bucket)**
Workloads with a Lakebase Opportunity Score ≥ 25. These are the immediate PoC and Phase 2 Wave 1 targets: high pain, high business impact, low complexity.

**Pro warehouse**
A SQL Warehouse type with dedicated, always-warm compute. Recommended for app backends with SLA requirements and high-concurrency workloads. More predictable latency than Serverless; higher baseline cost.

## S

**Schema (Unity Catalog)**
The second level in the `catalog.schema.table` hierarchy. Equivalent to a database schema or namespace. Group tables by domain or team (`prod.sales`, `prod.ml`, `prod.ops`).

**Serverless warehouse**
A SQL Warehouse type where compute starts and stops automatically. Billed per second of actual usage. Best for analytics, BI dashboards, and ad-hoc queries. Auto-starts add 10–30s latency on cold requests.

**Service principal**
A non-human identity for automated workloads (pipelines, applications). Recommended over PATs for production connections. Managed in Databricks account settings.

## T

**Time travel**
Delta Lake's ability to query a table as it existed at a previous point in time: `SELECT * FROM table TIMESTAMP AS OF '2026-01-01'` or `SELECT * FROM table VERSION AS OF 5`. Retained for the VACUUM retention period (default: 7 days).

**Trust Foundations**
Blueprint's name for the five governance and compliance prerequisites that must be in place before migrating a workload: SQL Compatibility, Access Control, Data Inventory, Compliance & Governance, Data Quality Baseline.

## U

**Unity Catalog**
Databricks' centralized data governance layer. Provides three-level namespacing (`catalog.schema.table`), role-based access control (GRANT/REVOKE), column masking, row filters, data lineage, and audit logging — all in one place.

## V

**VACUUM**
The Delta Lake command that removes files no longer needed for time travel queries. Run after OPTIMIZE. Default retention: 7 days (`RETAIN 168 HOURS`). Do not set retention below 7 days on production tables.

## W

**Watermark (streaming)**
A threshold used in Structured Streaming to bound how late arriving data can be. `withWatermark("event_ts", "5 minutes")` tells Spark to wait up to 5 minutes for late events before finalizing a window aggregate.

## Z

**Z-order**
A data layout optimization that co-locates rows with similar values in the same files, enabling Delta Lake to skip irrelevant files when filtering. Apply with `OPTIMIZE table ZORDER BY (col1, col2)`. Best for analytics tables filtered on 1–3 high-cardinality columns.

**Zero-copy sharing**
Databricks' ability to give multiple teams access to the same Delta tables without duplicating data. Analytics teams can query the same tables that application backends write to, using Unity Catalog grants to control access.
