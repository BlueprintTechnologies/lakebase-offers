# Heavy ETL — Refactor First

For workloads that rely heavily on procedural logic, complex UDFs, or database-specific features that have no direct Databricks SQL equivalent. These workloads cannot be migrated by query translation alone. Typical effort: 8–12 weeks.

## What qualifies

- Stored procedures with complex business logic (> 50 lines of procedural SQL)
- Heavy UDF usage: Java, C, R, or proprietary UDFs not portable to Python/Scala
- Tight coupling to database-specific features: Oracle PL/SQL packages, SQL Server CLR, Snowflake JavaScript UDFs with DOM access
- Data pipeline orchestration embedded in the database (DBMS Scheduler, pg_cron, SQL Server Agent jobs)
- Binary or proprietary serialization formats not readable by Spark
- Workloads that fail the SQL Compatibility Check with multiple Critical-severity flags

If only Medium or Low flags exist, try [Analytics to Delta](analytics-to-delta.md) first — it may work with minor query modifications.

## Why "Refactor First"

The assessment scored this workload low for a reason: the migration complexity denominator is high. Direct translation without refactoring produces fragile, slow Databricks jobs that mirror the old anti-patterns. The investment in refactoring pays back in:

- Simpler maintenance (Spark + Python/SQL replaces procedural DB logic)
- Better performance (Spark is distributed; stored procedures are serial)
- Full access to Delta features (time travel, CDC, zero-copy sharing)
- Cheaper compute (Databricks clusters vs. high-CPU database instances)

## Architecture after refactoring

```
Before:
  Source DB → Stored Procedures → Output Tables → Downstream Systems
              (serial, stateful,   (DB-native)
               proprietary UDFs)

After:
  Event Sources / Raw Data
         │
  Databricks Notebooks / DLT
  (distributed Python + SQL)
         │
  Delta Tables (Unity Catalog)
         │
  Databricks Workflows (orchestration)
         │
  Downstream Systems (BI, APIs, exports)
```

## The refactoring steps

### Step 1: Inventory all procedural logic

Before writing a line of code, map every stored procedure, UDF, scheduled job, and trigger in scope:

```sql
-- SQL Server: list all stored procedures
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE type = 'P'
ORDER BY name;

-- Oracle: list all packages and procedures
SELECT object_type, object_name, status
FROM all_objects
WHERE object_type IN ('PACKAGE', 'PROCEDURE', 'FUNCTION', 'TRIGGER')
  AND owner = 'MYSCHEMA'
ORDER BY object_type, object_name;

-- PostgreSQL: list all functions
SELECT routine_name, routine_type, data_type
FROM information_schema.routines
WHERE routine_schema = 'public'
ORDER BY routine_name;
```

For each procedure: record its name, purpose, inputs, outputs, dependencies, and estimated lines of logic. This inventory becomes the refactoring backlog.

### Step 2: Classify each procedure by migration path

| Type | Migration path |
| --- | --- |
| Simple transformation (filter, join, aggregate) | Rewrite as Databricks SQL or dbt model |
| Complex procedural logic (loops, cursors) | Rewrite as PySpark notebook |
| Orchestration logic (call A, then B, then C) | Replace with Databricks Workflow DAG |
| Business rule UDF (pure function, no side effects) | Rewrite as Python UDF or Spark SQL function |
| External system calls (email, HTTP, file writes) | Replace with Workflow task (notebook or webhook) |
| Triggers (row-level, reactive) | Replace with Delta Change Data Feed + Workflow |

### Step 3: Rewrite stored procedures as notebooks

**Pattern: cursor loop → PySpark transformation**

```python
# Before (Oracle PL/SQL — cursor loop updating rows one at a time)
# FOR rec IN (SELECT order_id, amount FROM orders WHERE status = 'pending') LOOP
#   IF rec.amount > 10000 THEN
#     UPDATE orders SET status = 'high_value', reviewed_by = 'auto' WHERE order_id = rec.order_id;
#   END IF;
# END LOOP;

# After (PySpark — vectorized, runs on distributed cluster)
from pyspark.sql import functions as F

spark.sql("""
  MERGE INTO prod.app.orders AS target
  USING (
    SELECT order_id, 'high_value' AS new_status, 'auto' AS reviewer
    FROM prod.app.orders
    WHERE status = 'pending' AND amount > 10000
  ) AS source
  ON target.order_id = source.order_id
  WHEN MATCHED THEN UPDATE SET
    status      = source.new_status,
    reviewed_by = source.reviewer
""")
```

**Pattern: proprietary UDF → Python UDF**

```python
# Before: Oracle custom function for address normalization (C extension)
# SELECT normalize_address(street, city, state) FROM customers;

# After: Python UDF registered in Unity Catalog
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType
import usaddress  # standard Python library

@udf(returnType=StringType())
def normalize_address(street, city, state):
    try:
        parsed, _ = usaddress.tag(f"{street} {city} {state}")
        return f"{parsed.get('AddressNumber','')} {parsed.get('StreetName','')} {city} {state}".strip()
    except Exception:
        return f"{street} {city} {state}"

# Register for use in SQL
spark.udf.register("normalize_address", normalize_address)

# Use in SQL
spark.sql("""
  SELECT normalize_address(street, city, state) AS normalized
  FROM prod.app.customers
""")
```

### Step 4: Replace scheduled jobs with Databricks Workflows

Map each DBMS scheduler job to a Databricks Workflow task:

```
# Before: Oracle DBMS_SCHEDULER job (nightly at 2am)
#   step 1: EXEC archive_old_orders;
#   step 2: EXEC refresh_summary_tables;
#   step 3: EXEC send_daily_report;

# After: Databricks Workflow (JSON definition)
```

```json
{
  "name": "nightly_etl",
  "schedule": {
    "quartz_cron_expression": "0 0 2 * * ?",
    "timezone_id": "America/Chicago"
  },
  "tasks": [
    {
      "task_key": "archive_old_orders",
      "notebook_task": {
        "notebook_path": "/Shared/etl/archive_old_orders"
      }
    },
    {
      "task_key": "refresh_summaries",
      "depends_on": [{"task_key": "archive_old_orders"}],
      "notebook_task": {
        "notebook_path": "/Shared/etl/refresh_summary_tables"
      }
    },
    {
      "task_key": "daily_report",
      "depends_on": [{"task_key": "refresh_summaries"}],
      "notebook_task": {
        "notebook_path": "/Shared/etl/send_daily_report"
      }
    }
  ]
}
```

### Step 5: Replace triggers with Change Data Feed

Database triggers that react to row changes are replaced by reading Delta's Change Data Feed:

```python
# Before: SQL Server trigger that fires on INSERT to orders
# CREATE TRIGGER trg_order_insert ON orders
# AFTER INSERT AS
#   INSERT INTO audit_log (action, order_id, ts) SELECT 'INSERT', order_id, GETDATE() FROM inserted;

# After: Databricks Streaming job that reads Delta CDF
orders_cdf = (
    spark.readStream
    .format("delta")
    .option("readChangeFeed", "true")
    .option("startingVersion", "latest")
    .table("prod.app.orders")
)

def write_audit_log(batch_df, batch_id):
    inserts = batch_df.filter("_change_type = 'insert'")
    audit_rows = inserts.select(
        F.lit("INSERT").alias("action"),
        "order_id",
        F.current_timestamp().alias("ts")
    )
    audit_rows.write.format("delta").mode("append").saveAsTable("prod.app.audit_log")

orders_cdf.writeStream \
    .foreachBatch(write_audit_log) \
    .option("checkpointLocation", "/checkpoints/audit_log") \
    .trigger(processingTime="30 seconds") \
    .start()
```

### Step 6: Data type migration for proprietary formats

If the source workload uses binary, custom, or proprietary column types:

| Source type | Migration path |
| --- | --- |
| Oracle RAW / BLOB | Export as base64 STRING; decode in application |
| SQL Server HIERARCHYID | Convert to STRING path representation |
| SQL Server GEOGRAPHY / GEOMETRY | Export as WKT STRING; use H3 or sedona for spatial ops |
| PostgreSQL ARRAY | Map to `ARRAY<type>` in Delta |
| PostgreSQL HSTORE | Map to `MAP<STRING, STRING>` in Delta |
| Snowflake VARIANT | Map to STRING (JSON); parse with `from_json()` |

### Step 7: Parallel validation

Run old and new pipelines in parallel for 2–4 weeks before cutover:

```python
# Automated parallel comparison (run nightly)
def compare_pipeline_outputs(table: str, key_col: str, numeric_cols: list):
    source_df = spark.read.format("jdbc").option("dbtable", f"source.{table}").load()
    target_df = spark.table(f"prod.etl.{table}")

    # Row count
    source_cnt = source_df.count()
    target_cnt = target_df.count()
    print(f"{table}: source={source_cnt}, lakebase={target_cnt}, diff={abs(source_cnt-target_cnt)}")

    # Numeric column sums
    for col in numeric_cols:
        s_sum = source_df.agg({col: "sum"}).collect()[0][0]
        t_sum = target_df.agg({col: "sum"}).collect()[0][0]
        pct_diff = abs(s_sum - t_sum) / s_sum * 100 if s_sum else 0
        status = "OK" if pct_diff < 0.01 else "MISMATCH"
        print(f"  {col}: {status} ({pct_diff:.4f}% diff)")
```

### Step 8: Cutover

Heavy ETL workloads require a planned cutover window (typically a weekend):

```
T-7 days:  Stakeholder sign-off on parallel validation results
T-2 days:  Final runbook review with data engineering team
T-0 (Friday 6pm):
  1. Disable source DBMS scheduler jobs
  2. Run final full load / MERGE from source to Lakebase
  3. Enable Databricks Workflows
  4. Validate row counts and spot-check outputs
  5. Redirect downstream consumers (BI tools, API connections)
  6. Monitor for 4 hours; escalate if error rate > 0.1%
T+72h: Source workload decommission decision
```

## Common refactoring pitfalls

**NULL handling differences:** Databricks SQL follows ANSI NULL semantics. `NULL != NULL` evaluates to `NULL`, not `FALSE`. Test all `WHERE` clauses that filter on nullable columns.

**String case sensitivity:** Databricks SQL comparisons are case-sensitive by default. Source platforms (especially MySQL) may be case-insensitive. Add `LOWER()` wrapping where needed.

**Date arithmetic:** Each platform uses different functions. Use the [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) function mapping tables.

**Transaction scope:** Stored procedures often wrap multi-statement operations in a transaction. In Databricks SQL, each MERGE/UPDATE/DELETE is atomic, but multi-statement transactions require explicit `BEGIN`/`COMMIT` (available in Databricks SQL 12.2+).

## Related

- SQL function translation reference: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- Delta Change Data Feed (replacing triggers): [Delta Lake](../databricks-101/delta-lake.md)
- Orchestration with Workflows: [App Backends](app-backends.md) — Step 6
- Validating complex migrations: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
