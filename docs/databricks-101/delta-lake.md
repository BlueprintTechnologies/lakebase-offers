# Delta Lake

Delta Lake is the open table format that stores your data in Databricks. Every table you migrate to Lakebase is stored as a Delta table — Parquet files in your cloud storage, plus a transaction log that gives you ACID guarantees and time travel.

## What it is

Delta Lake is an open-source storage layer that lives on top of cloud object storage (S3, ADLS, GCS). It adds:

- **ACID transactions** — reads and writes are atomic. No partial updates visible to concurrent readers.
- **Schema enforcement** — the table schema is enforced on write; bad data is rejected.
- **Schema evolution** — you can add or rename columns without rewriting the table.
- **Time travel** — every version of a table is retained for a configurable window; you can query any past state.
- **Scalable metadata** — handles tables with billions of rows and millions of files efficiently.

## Why Delta Lake matters for migration

Your source platform (Snowflake, Oracle, etc.) stores data in its own proprietary format. When you migrate to Lakebase, your data is converted to Delta format. The benefits:

- **No lock-in.** Delta tables are Parquet files plus a JSON transaction log. Any tool that reads Parquet can read Delta (Spark, DuckDB, Trino, pandas).
- **Open format.** If you ever leave Databricks, your data comes with you.
- **Performance.** Delta's built-in optimization (Z-ordering, liquid clustering, auto-compaction) often makes queries faster than the source platform without manual tuning.
- **Cost efficiency.** Parquet in object storage is cheaper than proprietary storage. This is part of why migrations produce 40–80% storage cost reduction.

## Core operations

### CREATE TABLE

```sql
-- Create a managed Delta table (Databricks owns the data lifecycle)
CREATE TABLE catalog.schema.orders (
  order_id     STRING NOT NULL,
  customer_id  STRING NOT NULL,
  amount       DECIMAL(10,2),
  created_at   TIMESTAMP,
  region       STRING
)
USING DELTA
PARTITION BY (region);

-- Create an external Delta table (you own the storage path)
CREATE TABLE catalog.schema.orders_external
USING DELTA
LOCATION 's3://my-bucket/tables/orders';
```

### MERGE (UPSERT)

```sql
-- Merge new data into an existing table
MERGE INTO catalog.schema.customers AS target
USING staging.new_customers AS source
ON target.customer_id = source.customer_id
WHEN MATCHED THEN
  UPDATE SET
    email = source.email,
    updated_at = source.updated_at
WHEN NOT MATCHED THEN
  INSERT (customer_id, email, created_at, updated_at)
  VALUES (source.customer_id, source.email, source.created_at, source.updated_at);
```

### Time travel

```sql
-- Query a table as of a specific timestamp
SELECT * FROM catalog.schema.orders
TIMESTAMP AS OF '2026-04-01 12:00:00';

-- Query a table as of a specific version number
SELECT * FROM catalog.schema.orders VERSION AS OF 42;

-- View history of all changes
DESCRIBE HISTORY catalog.schema.orders;
```

Time travel is invaluable for debugging post-migration issues — if you discover a data discrepancy, you can query the table as of an earlier version to isolate when it appeared.

### OPTIMIZE and Z-ORDER

```sql
-- Compact small files (improves scan performance)
OPTIMIZE catalog.schema.orders;

-- Z-order by columns frequently used in WHERE clauses
-- (co-locates related data in fewer files; speeds up filtered queries)
OPTIMIZE catalog.schema.orders ZORDER BY (customer_id, created_at);
```

Run OPTIMIZE weekly or after large data loads. Most Lakebase SQL Warehouses also run auto-optimize in the background.

### VACUUM (delete old versions)

```sql
-- Remove file versions older than 30 days
-- (default retention is 7 days; extend for time-travel or right-to-delete workflows)
VACUUM catalog.schema.orders RETAIN 720 HOURS;
```

> **Caution:** VACUUM is irreversible. Do not run it with a retention shorter than your time-travel window.

## Delta table properties

Control table behavior through TBLPROPERTIES:

```sql
-- Set time travel retention to 90 days
ALTER TABLE catalog.schema.orders
  SET TBLPROPERTIES ('delta.logRetentionDuration' = 'interval 90 days');

-- Enable auto-optimize (merge small files automatically)
ALTER TABLE catalog.schema.orders
  SET TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true',
                     'delta.autoOptimize.autoCompact' = 'true');

-- Enable change data feed (capture row-level changes for downstream consumers)
ALTER TABLE catalog.schema.orders
  SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

## Delta vs. Parquet vs. other formats

| Format | ACID | Schema enforcement | Time travel | Partition evolution | Open |
| --- | --- | --- | --- | --- | --- |
| **Delta Lake** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Apache Iceberg** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Apache Hudi** | ✅ | ✅ | ✅ | Partial | ✅ |
| **Parquet (raw)** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **CSV / JSON** | ❌ | ❌ | ❌ | ❌ | ✅ |

Databricks supports reading Iceberg tables through its Iceberg catalog integration. Delta and Iceberg are the two dominant open table formats; Delta is the native format for Databricks and the format your migration targets.

## Related

- Lakebase SQL (the query engine on Delta): [Lakebase SQL](lakebase-sql.md)
- Governance on Delta tables: [Unity Catalog](unity-catalog.md)
- Storage cost model: [DBUs and Billing](dbus-and-billing.md)
- Delta Lake documentation: [docs.delta.io](https://docs.delta.io)
- Databricks Delta docs: [docs.databricks.com/en/delta](https://docs.databricks.com/en/delta/index.html)
