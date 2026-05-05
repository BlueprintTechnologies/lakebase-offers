# App Backends

For operational data serving user-facing applications: user profiles, orders, inventory, subscriptions. Full ACID semantics, moderate concurrency. Typical effort: 3–6 weeks.

## What qualifies

- Transactional reads and writes (INSERT, UPDATE, DELETE, MERGE)
- Moderate concurrency: 50–1000 concurrent connections from app servers
- Latency: 10–200ms acceptable (not hard real-time)
- Data freshness: real-time or near-real-time (not batch)
- Source: PostgreSQL, MySQL, Oracle, SQL Server

## Architecture

```
Application servers
        │  (connection pooling)
   Load balancer
        │
  Lakebase SQL Warehouse
   (Pro tier, auto-scaling)
        │
    Delta Tables
  (ACID transactions)
        │
  Zero-copy reads ──→  Analytics / BI / Reporting
```

Key difference from Analytics workloads: the warehouse needs to be Pro tier (not Serverless) if you have SLA requirements, because Pro provides more consistent concurrency behavior.

## The migration steps

### Step 1: Schema migration with constraints

```sql
-- Create the Delta table with primary key constraint (informational in Delta, enforced by app)
CREATE TABLE prod.app.users (
  user_id      STRING NOT NULL,
  email        STRING NOT NULL,
  name         STRING,
  status       STRING DEFAULT 'active',
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP
)
USING DELTA
CLUSTER BY (user_id)
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');  -- for downstream CDC consumers

-- Declare primary key (informational; helps tools understand the model)
ALTER TABLE prod.app.users
  ADD CONSTRAINT pk_users PRIMARY KEY (user_id);

-- Declare foreign key
ALTER TABLE prod.app.orders
  ADD CONSTRAINT fk_orders_users
  FOREIGN KEY (user_id) REFERENCES prod.app.users (user_id);
```

> **Note:** Delta Lake foreign keys are informational (not enforced on write). Your application must enforce referential integrity if required.

### Step 2: Initial data load

```python
# For PostgreSQL source (adapt for MySQL, Oracle, etc.)
df = spark.read \
  .format("jdbc") \
  .option("url", "jdbc:postgresql://host:5432/mydb") \
  .option("dbtable", "public.users") \
  .option("user", "reader") \
  .option("password", "<password>") \
  .option("fetchsize", "10000") \
  .load()

df.write.format("delta").mode("overwrite").saveAsTable("prod.app.users")
```

### Step 3: Set up real-time sync (parallel run period)

During validation, run both source and Lakebase in parallel with CDC sync:

```python
# Databricks DLT (Delta Live Tables) for CDC from PostgreSQL via Debezium/Kafka
import dlt

@dlt.table(name="users_cdc")
def users_cdc():
    return spark.readStream \
      .format("kafka") \
      .option("kafka.bootstrap.servers", "kafka:9092") \
      .option("subscribe", "postgres.public.users") \
      .load()

@dlt.table(name="users")
def users():
    return dlt.read_stream("users_cdc") \
      .select(...)  # parse Debezium envelope
```

Or use Databricks Lakeflow Connect for common source integrations.

### Step 4: Validate ACID behavior

Test the three critical ACID scenarios:

```python
# Test 1: Concurrent UPDATE correctness
import threading

def update_user(user_id, new_email):
    cursor.execute(
      f"UPDATE prod.app.users SET email='{new_email}', updated_at=now() WHERE user_id='{user_id}'"
    )

# Run 50 concurrent updates — none should produce a dirty read
threads = [threading.Thread(target=update_user, args=(f"user_{i}", f"new_{i}@test.com"))
           for i in range(50)]
[t.start() for t in threads]
[t.join() for t in threads]

# Verify: all 50 users have a non-null updated_at
cursor.execute("SELECT COUNT(*) FROM prod.app.users WHERE updated_at IS NULL AND user_id LIKE 'user_%'")
assert cursor.fetchone()[0] == 0, "ACID violation: some updates produced NULLs"

# Test 2: Row count after concurrent inserts
# Start N threads, each inserting M rows
# Final count must equal N × M

# Test 3: Failed transaction does not persist
# Start a transaction, insert rows, throw exception before commit
# Verify rows do not appear in the table
```

### Step 5: Configure connection pooling

Lakebase SQL Warehouses use HTTP/2 for connections. For high-concurrency app backends, configure connection pooling at the application layer:

```python
# Python: use a connection pool
from databricks import sql
from databricks.sql.auth.auth import AccessTokenAuth

pool = []
POOL_SIZE = 20

for _ in range(POOL_SIZE):
    conn = sql.connect(
        server_hostname="<workspace>.databricks.com",
        http_path="/sql/1.0/warehouses/<warehouse-id>",
        auth_provider=AccessTokenAuth("<token>"),
        max_download_threads=4
    )
    pool.append(conn)
```

For Java/Scala applications, use the Databricks JDBC driver with a standard HikariCP connection pool.

### Step 6: Replicate stored procedures as workflows

If the source application relies on stored procedures for business logic, migrate each procedure to a Databricks Workflow:

```
# Source: Oracle stored procedure (nightly user deactivation)
# → Databricks Workflow: daily scheduled notebook
#   notebook step 1: identify inactive users
#   notebook step 2: MERGE status = 'inactive'
#   notebook step 3: send notification (webhook)
```

### Step 7: Update app connection strings

```python
# Before (PostgreSQL)
import psycopg2
conn = psycopg2.connect(host="postgres-host", dbname="mydb", user="app", password="secret")

# After (Lakebase)
from databricks import sql
conn = sql.connect(
    server_hostname="<workspace>.databricks.com",
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    access_token="<token>"
)
```

The SQL dialect change is minimal — standard CRUD operations work identically.

## Zero-copy sharing for analytics

Once the app backend data is in Delta, analytics teams can access it without any data pipeline:

```sql
-- Grant analytics team read access (no data copy needed)
GRANT SELECT ON TABLE prod.app.orders TO `analytics-team`;

-- Analytics can immediately query the same data the app is writing to
SELECT DATE(created_at), region, SUM(amount)
FROM prod.app.orders
GROUP BY 1, 2
ORDER BY 1 DESC;
```

This is one of the highest-value outcomes of an app backend migration: the analytics team no longer needs a nightly export from the application database.

## Related

- For read-heavy analytics on the same tables: [Analytics to Delta](analytics-to-delta.md)
- For high-volume single-row reads: [Point Lookups + Cache](point-lookups.md)
- ACID transactions: [Delta Lake](../databricks-101/delta-lake.md)
