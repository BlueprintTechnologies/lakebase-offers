# Analytics to Delta

The fastest migration path. Analytics workloads — reports, dashboards, aggregations — migrate to Lakebase with minimal query changes. Typical effort: 1–2 weeks.

## What qualifies

- Read-heavy SQL: SELECT, GROUP BY, window functions, joins across fact/dimension tables
- Query runtime: minutes to hours (or sub-minute for dashboards)
- Data update frequency: hourly to daily batch (not real-time streaming)
- Users: analysts, BI tools, embedded dashboards, data scientists
- No sub-second latency requirement

If the workload has point lookups (single-row, by primary key) or requires < 100ms response time, use [Point Lookups + Cache](point-lookups.md) instead.

## The migration steps

### Step 1: Export the schema

```sql
-- On your source platform: export the DDL for each table in scope
-- (Snowflake example)
SELECT GET_DDL('TABLE', 'schema.orders');

-- Or use the assessor output (assessment.json contains schema definitions)
```

### Step 2: Create Delta tables in Unity Catalog

Translate the source DDL to Delta. Map data types using the [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) reference:

```sql
-- Snowflake → Delta example
-- Source (Snowflake):
-- CREATE TABLE orders (
--   order_id VARCHAR(36) NOT NULL,
--   customer_id VARCHAR(36),
--   amount NUMBER(10,2),
--   created_at TIMESTAMP_NTZ
-- );

-- Delta equivalent:
CREATE TABLE prod.sales.orders (
  order_id     STRING NOT NULL,
  customer_id  STRING,
  amount       DECIMAL(10,2),
  created_at   TIMESTAMP
)
USING DELTA
PARTITION BY (DATE(created_at))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true'
);
```

### Step 3: Load data

**Full load (for tables ≤ 500 GB):**

```python
# Using Databricks spark session
df = spark.read \
  .format("jdbc") \
  .option("url", "jdbc:snowflake://<account>.snowflakecomputing.com/") \
  .option("dbtable", "schema.orders") \
  .option("user", "<user>") \
  .option("password", "<password>") \
  .load()

df.write \
  .format("delta") \
  .mode("overwrite") \
  .saveAsTable("prod.sales.orders")
```

**Incremental load (for tables > 500 GB or with SLA requirements):**

```python
# Load only new or changed rows using a watermark column
last_loaded = spark.sql(
  "SELECT MAX(created_at) FROM prod.sales.orders"
).collect()[0][0]

df_new = spark.read \
  .format("jdbc") \
  .option("dbtable", f"(SELECT * FROM schema.orders WHERE created_at > '{last_loaded}') t") \
  .load()

df_new.write \
  .format("delta") \
  .mode("append") \
  .saveAsTable("prod.sales.orders")
```

### Step 4: Validate row counts

```sql
-- Run on both platforms; must match
-- Source:
SELECT COUNT(*) FROM schema.orders;
-- Lakebase:
SELECT COUNT(*) FROM prod.sales.orders;
```

If counts differ, check for in-flight writes during the load window. Load again with a more recent watermark.

### Step 5: Validate query outputs

Pick the 3–5 most important queries for this workload and run them on both platforms. Results must match within 0.01% on numeric aggregations:

```sql
-- Sample validation query (run on both platforms)
SELECT
  DATE(created_at) AS day,
  region,
  COUNT(*) AS order_count,
  SUM(amount) AS total_amount,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY DATE(created_at), region
ORDER BY day, region;
```

### Step 6: Optimize the Delta table

```sql
-- Compact small files and co-locate frequently filtered data
OPTIMIZE prod.sales.orders ZORDER BY (customer_id, created_at);

-- Update table statistics for the query optimizer
ANALYZE TABLE prod.sales.orders COMPUTE STATISTICS FOR ALL COLUMNS;
```

### Step 7: Update connection strings

Update BI tools, dashboards, and pipeline connection strings to point at the Lakebase SQL Warehouse. For most tools, this is a server hostname + HTTP path change; the SQL itself does not change.

| Tool | What to update |
| --- | --- |
| Tableau | Data source connection: server + warehouse HTTP path |
| Power BI | Dataset connection |
| Looker | Connection settings |
| dbt | `profiles.yml` target |
| Python scripts | Connection string / SDK initialization |

### Step 8: Monitor for 72 hours

Run the source and Lakebase workloads in parallel for 72 hours. Compare:
- Row counts on new data loads
- Query output spot checks
- P95 latency
- Error rate

After 72 hours with no issues, decommission the source workload.

## Latency optimization

If initial performance is slower than expected:

**Enable result caching:**
Lakebase caches identical query results automatically for Serverless warehouses. For repeated dashboard queries, cache hit rate typically reaches 60–80% within a day of production traffic.

**Z-order by filter columns:**
```sql
OPTIMIZE prod.sales.orders ZORDER BY (region, customer_id);
-- Run after every large data load
```

**Increase warehouse size:**
If P95 > SLA target and Z-ordering does not help, bump up the warehouse size by one tier. Re-measure.

**Bloom filters for high-cardinality lookups:**
```sql
ALTER TABLE prod.sales.orders
  SET TBLPROPERTIES ('delta.bloomFilter.customer_id.enabled' = 'true',
                     'delta.bloomFilter.customer_id.fpp'     = '0.1');
```

## Related

- Data type mapping: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- If the workload has high-concurrency point lookups: [Point Lookups + Cache](point-lookups.md)
- Validating the migration: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
