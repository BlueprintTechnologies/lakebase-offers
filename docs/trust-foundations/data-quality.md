# Data Quality Baseline

Establish a data quality baseline on your source platform before migration. Without it, you cannot distinguish post-migration data issues from pre-existing ones — and every anomaly becomes a migration incident.

## What this foundation closes

- Unknown null rates that cause post-migration surprises
- Type coercion differences between source and Delta
- Duplicate key behavior that differs from Delta's semantics
- Baseline metrics needed to validate migration correctness

## The quality baseline checklist

Run these checks on each table in your PoC scope **before** the migration sprint:

### Row count and growth

- [ ] Total row count recorded (date + count)
- [ ] Row count trend (growing, stable, declining)
- [ ] Rows per partition or date range (for time-partitioned tables)

### Null rates

- [ ] Null rate per column recorded
- [ ] Columns with > 5% nulls flagged for review
- [ ] Nullable vs. NOT NULL constraints documented

### Distinct value counts (cardinality)

- [ ] Primary key columns verified as unique (0 duplicates)
- [ ] High-cardinality columns identified (customer_id, product_id)
- [ ] Low-cardinality flag columns checked for unexpected values

### Data type validation

- [ ] Numeric columns: min, max, mean recorded
- [ ] Date columns: min/max dates, null date rates
- [ ] String columns: max length, character set issues (encoding)
- [ ] JSON/semi-structured columns: key inventory, nesting depth

### Referential integrity

- [ ] Foreign key join rates checked (% of rows that join successfully)
- [ ] Orphaned records identified and documented

## Running the baseline

### Sample baseline SQL (generic, adapt to your platform)

```sql
-- Row count and date range
SELECT
  COUNT(*) AS row_count,
  MIN(created_at) AS earliest_row,
  MAX(created_at) AS latest_row,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM schema.customer_transactions;

-- Null rates per column (repeat for each column of interest)
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) AS email_nulls,
  ROUND(100.0 * SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS email_null_pct,
  SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS customer_id_nulls
FROM schema.customers;

-- Duplicate primary key check
SELECT customer_id, COUNT(*) AS cnt
FROM schema.customers
GROUP BY customer_id
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 10;

-- Numeric column stats
SELECT
  MIN(revenue) AS min_rev,
  MAX(revenue) AS max_rev,
  AVG(revenue) AS avg_rev,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue) AS median_rev,
  STDDEV(revenue) AS stddev_rev
FROM schema.orders;
```

Save baseline results to a CSV or table. You will run the same queries on Lakebase after migration to validate match.

## Delta-specific behavior differences to check for

Before migrating, verify how your source platform behaves vs. Delta on these edge cases:

| Behavior | Source platform | Delta Lake | Action |
| --- | --- | --- | --- |
| **NULL handling in aggregations** | Most: NULL ignored in SUM/AVG | Delta: same (NULL ignored) | No action for standard SQL |
| **NULL in joins** | Most: NULL != NULL in joins | Delta: same | No action |
| **String comparison case sensitivity** | Snowflake: case-insensitive by default | Delta: case-sensitive | Review WHERE clause string filters |
| **Timestamp precision** | Varies (microseconds vs. nanoseconds) | Delta: microsecond precision | Validate timestamp-based filters |
| **FLOAT rounding** | Platform-specific | IEEE 754 in Delta | Validate computed columns with FLOAT |
| **Duplicate rows on merge** | Some platforms deduplicate | Delta: preserves duplicates by default | Use `MERGE` with explicit dedup logic if needed |
| **Integer overflow** | Silent truncation on some platforms | Delta: raises error | Check MAX values for INT columns vs. BIGINT |

## Post-migration validation queries

After migrating to Lakebase, run these against both platforms and compare:

```sql
-- Run on source and Lakebase; results must match
SELECT
  DATE(created_at) AS day,
  COUNT(*) AS rows,
  SUM(revenue) AS total_revenue,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM transactions
WHERE created_at >= '2026-01-01'
GROUP BY DATE(created_at)
ORDER BY day;
```

A mismatch in any column is a finding. Common causes:

- **Row count mismatch:** Check for in-flight writes during migration, or duplicates introduced by the load job
- **Revenue sum mismatch:** Float rounding difference or NULL handling difference
- **Unique customer mismatch:** Case sensitivity in customer_id string comparison

## What to do with quality findings

If the baseline reveals data quality issues (high null rates, duplicates, referential integrity gaps), you have two choices:

1. **Fix before migration.** Clean the data on the source platform, then migrate clean data. Adds time but results in a cleaner Lakebase instance.
2. **Migrate as-is, document as known issues.** Migrate the data in its current state and track the quality issues in your data quality backlog for remediation on Lakebase.

Option 2 is faster for the PoC. Option 1 is better for long-term governance. Blueprint's recommendation: migrate as-is for the PoC, fix on Lakebase as part of Phase 2 using Delta constraints and data quality frameworks (Great Expectations, Databricks Expectations).

## Related

- Data type mapping: [SQL Compatibility Check](sql-compatibility.md)
- After migration, validate continuously: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
- Delta Lake data model: [Delta Lake](../databricks-101/delta-lake.md)
