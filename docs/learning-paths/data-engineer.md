# Data Engineer Learning Path

For data engineers and backend developers who will execute the migration: translating SQL, rewriting pipelines, configuring warehouses, and validating data correctness.

## What you own in the migration

| Task | Your responsibility |
| --- | --- |
| SQL compatibility review | Run the assessor's compatibility scan; resolve Critical and High flags |
| Schema translation | Recreate source DDL as Delta tables in Unity Catalog |
| Data loading | Initial full load + incremental sync |
| Pipeline rewrite | Translate stored procedures, UDFs, scheduled jobs |
| Validation | Row counts, aggregation correctness, ACID behavior |
| Performance tuning | OPTIMIZE, ZORDER, bloom filters, warehouse sizing |
| Connection cutover | Update application and pipeline connection strings |

## Before you touch anything

Complete the [Trust Foundations](../trust-foundations/index.md) in order:

1. [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) — find blocking incompatibilities before you invest in schema creation
2. [Access Control Review](../trust-foundations/access-control.md) — map source grants to Unity Catalog; don't recreate security debt
3. [Data Inventory & Schema Docs](../trust-foundations/data-inventory.md) — document what you're migrating; surprises during migration are expensive
4. [Compliance & Governance](../trust-foundations/compliance.md) — if PII is involved, masking must be in place before data lands in Unity Catalog
5. [Data Quality Baseline](../trust-foundations/data-quality.md) — capture source-side statistics before migration so you have a comparison baseline

## SQL you'll write constantly

**MERGE (replacing INSERT + UPDATE patterns):**
```sql
MERGE INTO prod.app.orders AS target
USING staging.orders_delta AS source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

**Liquid Clustering (replacing partition by for OLTP tables):**
```sql
CREATE TABLE prod.app.customers (...)
USING DELTA
CLUSTER BY (customer_id);   -- not PARTITION BY
```

**Z-ordering (for analytics tables with filter patterns):**
```sql
OPTIMIZE prod.sales.orders ZORDER BY (customer_id, region);
```

**Bloom filters (for high-cardinality point lookups):**
```sql
ALTER TABLE prod.ops.customers
  SET TBLPROPERTIES (
    'delta.bloomFilter.customer_id.enabled' = 'true',
    'delta.bloomFilter.customer_id.fpp'     = '0.01'
  );
```

**Time travel (debugging and validation):**
```sql
-- What did this table look like 24 hours ago?
SELECT * FROM prod.app.orders VERSION AS OF 10;
SELECT * FROM prod.app.orders TIMESTAMP AS OF '2026-05-01 00:00:00';
```

Full Delta SQL reference: [Delta Lake](../databricks-101/delta-lake.md).

## Connection setup

**Python (psycopg2 → databricks-sql-connector):**
```python
# Before
import psycopg2
conn = psycopg2.connect(host="postgres-host", dbname="mydb", user="app", password="...")

# After
from databricks import sql
conn = sql.connect(
    server_hostname="<workspace>.azuredatabricks.net",
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    access_token="<pat-token>"
)
```

**Python with connection pool:**
```python
from databricks import sql
from queue import Queue

pool = Queue()
for _ in range(20):
    pool.put(sql.connect(
        server_hostname="<workspace>.azuredatabricks.net",
        http_path="/sql/1.0/warehouses/<warehouse-id>",
        access_token="<token>"
    ))

conn = pool.get()
try:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
finally:
    pool.put(conn)
```

**Java/JDBC (HikariCP):**
```java
HikariConfig config = new HikariConfig();
config.setJdbcUrl("jdbc:databricks://<workspace>.azuredatabricks.net:443/default;transportMode=http;ssl=1;httpPath=/sql/1.0/warehouses/<id>");
config.setUsername("token");
config.setPassword("<pat-token>");
config.setMaximumPoolSize(20);
HikariDataSource ds = new HikariDataSource(config);
```

## Common SQL translation patterns

| Source platform | Source syntax | Databricks SQL equivalent |
| --- | --- | --- |
| Snowflake | `DATEADD(day, 7, created_at)` | `created_at + INTERVAL 7 DAYS` |
| Snowflake | `IFF(condition, true_val, false_val)` | `IF(condition, true_val, false_val)` |
| BigQuery | `DATE_DIFF(d1, d2, DAY)` | `DATEDIFF(d1, d2)` |
| Oracle | `ROWNUM <= 10` | `LIMIT 10` |
| SQL Server | `TOP 10` | `LIMIT 10` |
| Oracle | `NVL(col, default)` | `COALESCE(col, default)` |
| Redshift | `GETDATE()` | `CURRENT_TIMESTAMP` |

Full function mapping: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md).

## Validation checklist

Before marking any workload as migration-complete:

```
Data correctness:
[ ] Row count on Lakebase matches source (exact or within 0.01% for active tables)
[ ] 5 key aggregation queries produce matching results (< 0.01% numeric diff)
[ ] NULL counts per column match
[ ] Spot check 20 random rows match between source and target

Performance:
[ ] P95 latency meets or beats SLA target
[ ] Load test at 2× peak concurrency — no timeout errors
[ ] Cache hit rate ≥ 60% for read-heavy workloads

Reliability:
[ ] ACID test: 50 concurrent writes produce no dirty reads
[ ] Failed transaction test: partial writes do not persist
[ ] Connection pool handles 200 concurrent connections without exhaustion

Go-live:
[ ] Connection strings updated in all downstream consumers
[ ] Monitoring dashboards configured
[ ] 72-hour error rate < 0.1%
```

## Performance troubleshooting

**Slow queries:**
1. Run `EXPLAIN` to check if the query is using file pruning (look for `PartitionFilters`, `DataFilters`)
2. Verify CLUSTER BY or PARTITION BY matches the WHERE clause columns
3. Check if bloom filter is enabled on the lookup key
4. Run `ANALYZE TABLE ... COMPUTE STATISTICS FOR ALL COLUMNS` to update query optimizer stats
5. Scale up warehouse size by one tier; re-measure

**Slow MERGE:**
1. Large target tables: run `OPTIMIZE` before the MERGE
2. Check the MERGE predicate — it should match the clustering column
3. Use `spark.databricks.delta.merge.enableLowShuffle` = true for large merges

**Connection timeouts:**
1. Warehouse auto-stop is set too aggressively — increase idle timeout
2. Application is not using connection pooling — add pool
3. HTTP path is wrong — double-check warehouse ID in the path

More troubleshooting: [Troubleshooting](../troubleshooting.md).

## Related

- SQL dialect translation: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- Delta Lake features: [Delta Lake](../databricks-101/delta-lake.md)
- Migration playbooks by workload: [Migration Playbooks](../migration-playbooks/index.md)
- Post-migration validation: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
