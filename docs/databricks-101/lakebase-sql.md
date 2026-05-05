# Lakebase SQL

Lakebase SQL is Databricks' SQL engine — a high-performance, ANSI SQL-compatible query interface that runs on Delta Lake tables. It is what replaces your legacy data warehouse (Snowflake, Redshift, BigQuery, Oracle, etc.) in a Lakebase migration.

## What it is

Lakebase SQL is not a separate product. It is the SQL layer of the Databricks Lakehouse: you write standard SQL, Databricks runs it efficiently against Delta Lake tables stored in your cloud object storage. The compute engine (the SQL Warehouse) scales automatically; you pay per query rather than for an always-on cluster.

From a user perspective, Lakebase SQL looks like any other SQL database. You connect with JDBC/ODBC or the Databricks SDK, write queries, and get results. The difference is what runs underneath: instead of a proprietary query engine on proprietary storage, it is an open-source engine (Apache Spark SQL, optimized for interactive queries) on an open table format (Delta Lake, readable by dozens of other tools).

## What makes it different from your current platform

### Serverless compute

Traditional data warehouses charge for warehouse time — a running cluster costs money whether or not queries are running. Lakebase SQL Warehouses scale to zero between queries. You pay only for the seconds your queries are executing.

This is the primary source of the cost savings in your assessment: most Snowflake and Redshift customers' warehouses are idle 60–80% of the time they are running.

### Decoupled storage and compute

Your data lives in cloud object storage (S3, ADLS, GCS) in Delta format. Multiple SQL Warehouses — or any other Databricks service — can read the same data simultaneously without copying it. This is what "zero-copy sharing" means in your assessment report.

On Snowflake or BigQuery, sharing data typically means copying it. On Lakebase, sharing means granting access — the data does not move.

### SQL dialect compatibility

Lakebase SQL supports ANSI SQL and most commonly-used extensions. The [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) in your assessment tells you exactly which queries need changes. For most analytics workloads, the number is small.

## SQL Warehouses: the compute layer

A SQL Warehouse is the compute cluster that runs your Lakebase SQL queries. Three types:

| Type | Best for | Scaling |
| --- | --- | --- |
| **Serverless** | Interactive queries, dashboards, BI tools | Scales to zero; fastest startup (< 5 sec) |
| **Pro** | Concurrent workloads, predictable SLAs | Scales based on load; slower startup |
| **Classic** | Legacy workloads, custom configs | Manual or auto-scaling |

Most migrations start with Serverless for analytics workloads. Pro is used for high-concurrency or SLA-bound workloads.

### Connecting to a SQL Warehouse

Any tool that speaks JDBC or ODBC works:

```python
# Python — Databricks SDK
from databricks import sql

connection = sql.connect(
    server_hostname="<workspace>.databricks.com",
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    access_token="<your-token>"
)
cursor = connection.cursor()
cursor.execute("SELECT * FROM catalog.schema.my_table LIMIT 10")
print(cursor.fetchall())
```

```bash
# JDBC connection string (for BI tools)
jdbc:databricks://<workspace>.databricks.com:443/default;
  transportMode=http;ssl=1;
  httpPath=/sql/1.0/warehouses/<warehouse-id>;
  AuthMech=3;UID=token;PWD=<your-token>
```

### Connection strings for common BI tools

| Tool | Connection type | Reference |
| --- | --- | --- |
| Tableau | Databricks connector (native) | [Tableau docs](https://help.tableau.com/current/pro/desktop/en-us/examples_databricks.htm) |
| Power BI | Databricks connector (native) | [Power BI docs](https://learn.microsoft.com/en-us/power-bi/connect-data/service-azure-databricks) |
| Looker | Databricks dialect | [Looker docs](https://docs.looker.com/setup-and-management/database-config/databricks) |
| dbt | Databricks adapter | [dbt docs](https://docs.getdbt.com/docs/core/connect-data-platform/databricks-setup) |
| Excel | ODBC driver | [Databricks ODBC driver](https://docs.databricks.com/en/integrations/odbc/download.html) |

## What "Lakebase" means specifically

Databricks uses "Lakebase" to refer to the database capabilities of the Lakehouse — specifically the operational and transactional SQL features that make Databricks suitable for app backends and real-time workloads, not just analytics:

- **ACID transactions** on Delta tables (full INSERT, UPDATE, DELETE, MERGE)
- **Sub-second latency** for point lookups with caching
- **High-concurrency** query serving with connection pooling
- **Zero-copy sharing** across consumers without data duplication

When your assessment report says a workload should "migrate to Lakebase," it means: run this workload on Databricks SQL using these features, targeting the Lakebase runtime tier.

## Related

- Storage format: [Delta Lake](delta-lake.md)
- Governance layer: [Unity Catalog](unity-catalog.md)
- Cost model: [DBUs and Billing](dbus-and-billing.md)
- Databricks SQL docs: [docs.databricks.com/en/sql](https://docs.databricks.com/en/sql/index.html)
