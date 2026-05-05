# Data Analyst Learning Path

For data analysts, BI developers, and report authors who query the data and build dashboards. The migration changes where the data lives, not what it means — but some query syntax and connection steps will change.

## What changes for analysts

| Area | Before | After |
| --- | --- | --- |
| SQL dialect | Snowflake SQL / BigQuery SQL / T-SQL / Oracle SQL | Databricks SQL (ANSI + extensions) |
| Connection | Platform-specific JDBC/ODBC | Databricks SQL Warehouse JDBC/ODBC |
| Table names | `database.schema.table` | `catalog.schema.table` (3-level Unity Catalog namespace) |
| Date functions | Platform-specific (DATEADD, DATE_DIFF) | ANSI (+ INTERVAL syntax) |
| String functions | Minor differences (see below) | Mostly the same |
| Result caching | Platform-managed | Automatic for identical queries on Serverless warehouses |

Most analyst queries — SELECTs, GROUP BYs, JOINs, window functions — work identically. The main change is reconnecting your BI tool to the new warehouse.

## Reconnecting your BI tool

### Tableau

1. Open the workbook
2. Data → Edit Connection
3. Select "Databricks" from the connector list
4. Enter server hostname and HTTP path (from your platform admin)
5. Authenticate with your personal access token
6. Re-map any table references that changed namespace

### Power BI

1. Home → Transform Data → Data Source Settings
2. Find the old source connection; click Change Source
3. Select "Azure Databricks" (or "Databricks")
4. Enter workspace URL and HTTP path
5. Authenticate (OAuth or token)

### Looker

1. Admin → Connections → Edit the data connection
2. Update host, database, and authentication fields
3. Test connection; update PDT (Persistent Derived Table) settings if used

### dbt

In `profiles.yml`:
```yaml
my_profile:
  target: prod
  outputs:
    prod:
      type: databricks
      host: "<workspace>.azuredatabricks.net"
      http_path: "/sql/1.0/warehouses/<warehouse-id>"
      token: "{{ env_var('DBT_TOKEN') }}"
      schema: prod_sales        # your target schema
      threads: 4
```

### Direct SQL / Notebook

```python
from databricks import sql

conn = sql.connect(
    server_hostname="<workspace>.azuredatabricks.net",
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    access_token="<token>"
)
cursor = conn.cursor()
cursor.execute("SELECT * FROM prod.sales.orders WHERE region = 'us-west' LIMIT 100")
df = cursor.fetchall()
```

## SQL changes you may encounter

Most queries work without change. Watch for these patterns:

**Date arithmetic:**
```sql
-- Snowflake / SQL Server
SELECT DATEADD(day, -30, CURRENT_TIMESTAMP)

-- Databricks SQL
SELECT CURRENT_TIMESTAMP - INTERVAL 30 DAYS
-- or
SELECT DATE_SUB(CURRENT_DATE, 30)
```

**String splitting:**
```sql
-- Snowflake
SELECT SPLIT(col, ',')

-- Databricks SQL
SELECT SPLIT(col, ',')   -- same! SPLIT works identically
```

**Approximate distinct count:**
```sql
-- Snowflake
SELECT APPROX_COUNT_DISTINCT(user_id) FROM orders

-- Databricks SQL
SELECT APPROX_COUNT_DISTINCT(user_id) FROM orders  -- same function name
```

**Conditional aggregation:**
```sql
-- Standard (works everywhere)
SELECT COUNT(*) FILTER (WHERE status = 'active') AS active_count FROM users

-- Also works in Databricks SQL
SELECT SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count FROM users
```

**Table sampling:**
```sql
-- Snowflake
SELECT * FROM orders SAMPLE (10)

-- Databricks SQL
SELECT * FROM orders TABLESAMPLE (10 PERCENT)
```

For a full function-by-function mapping: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md).

## The 3-level table namespace

Databricks uses Unity Catalog with three levels: `catalog.schema.table`.

- **Catalog** — the top-level container (usually `prod`, `dev`, `staging`)
- **Schema** — equivalent to a database schema or namespace (e.g., `sales`, `finance`, `ops`)
- **Table** — the table name

If your old queries referenced `orders` or `sales.orders`, they now need to be `prod.sales.orders`. This is a find-and-replace in most BI tools — ask your platform admin what the catalog and schema names are.

```sql
-- Old (two-level)
SELECT * FROM sales.orders

-- New (three-level)
SELECT * FROM prod.sales.orders
```

## Understanding query performance

**Why was my query slower / faster after migration?**

Databricks uses different query optimization than most source platforms. Expect:

- **First-run slower:** Serverless warehouses auto-start; add 10–30s on cold start
- **Repeat queries faster:** Identical queries hit the result cache (no compute needed)
- **Large aggregations faster:** Databricks Photon engine is highly optimized for columnar aggregations
- **Point lookups comparable:** With bloom filters and liquid clustering in place, single-row lookups match PostgreSQL/MySQL performance

**Result cache:**
Lakebase caches the results of identical queries automatically. If you run the same dashboard query every 5 minutes, most runs hit the cache and cost no compute. The cache is invalidated when underlying data changes.

**Checking query history:**
```sql
-- Your recent queries and their performance
SELECT
  statement_text,
  start_time,
  total_time_ms,
  from_result_cache
FROM system.query.history
WHERE user_name = current_user()
  AND start_time >= NOW() - INTERVAL 24 HOURS
ORDER BY start_time DESC;
```

## Accessing data you couldn't before

One of the biggest wins after migration: analytics teams can query operational data (orders, users, inventory) directly from the same Delta tables the application writes to — no nightly export needed.

```sql
-- Live app data, no pipeline, no export lag
SELECT DATE(created_at), region, COUNT(*), SUM(amount)
FROM prod.app.orders
WHERE created_at >= NOW() - INTERVAL 7 DAYS
GROUP BY 1, 2
ORDER BY 1 DESC;
```

Access is controlled by Unity Catalog grants. If you need access to a table you can't currently query, ask your platform admin.

## Related

- Reconnecting BI tools: [Analytics to Delta playbook — Step 7](../migration-playbooks/analytics-to-delta.md#step-7-update-connection-strings)
- SQL function mapping: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- Lakebase SQL overview: [Lakebase SQL](../databricks-101/lakebase-sql.md)
- Unity Catalog and table access: [Unity Catalog](../databricks-101/unity-catalog.md)
