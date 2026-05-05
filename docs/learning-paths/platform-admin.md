# Platform Admin Learning Path

For database administrators, cloud platform engineers, and infrastructure teams who manage the Databricks workspace, Unity Catalog, and warehouse configuration.

## Your responsibilities in the migration

| Area | Tasks |
| --- | --- |
| Workspace setup | Create SQL Warehouses; configure auto-scaling and auto-stop |
| Unity Catalog | Create catalogs, schemas; set up metastore if not already done |
| Access control | Replicate source platform grants to Unity Catalog RBAC |
| Secrets management | Store credentials (tokens, service account keys) in Databricks Secrets |
| Networking | Configure private link, IP allowlists, or VPC peering if required |
| Monitoring | Set up system table queries, alerting, warehouse utilization dashboards |
| Warehouse sizing | Right-size warehouses for each workload type |
| Maintenance | Schedule OPTIMIZE, VACUUM, and statistics refresh jobs |

## Warehouse configuration by workload type

| Workload | Warehouse type | Size | Auto-stop |
| --- | --- | --- | --- |
| Analytics / BI | Serverless | Medium | 10 min |
| App backends (SLA) | Pro | Large | 60 min |
| Point lookups (high QPS) | Pro | Large or X-Large | 120 min |
| Agent state / Feature serving | Pro | X-Large | 120 min |
| Streaming aggregations | Pro | Large | Never (always-on) |
| Interactive / ad-hoc | Serverless | Small | 5 min |

Create warehouses with Terraform or the Databricks CLI:

```bash
# Create a Pro warehouse for app backends
databricks warehouses create \
  --name "app-backends-prod" \
  --cluster-size "Large" \
  --warehouse-type PRO \
  --auto-stop-mins 60 \
  --min-num-clusters 1 \
  --max-num-clusters 3 \
  --enable-serverless-compute false
```

Or in Terraform:
```hcl
resource "databricks_sql_endpoint" "app_backend" {
  name             = "app-backends-prod"
  cluster_size     = "Large"
  warehouse_type   = "PRO"
  auto_stop_mins   = 60
  min_num_clusters = 1
  max_num_clusters = 3
}
```

## Unity Catalog setup

### Metastore and catalog

```sql
-- Create the production catalog (run as metastore admin)
CREATE CATALOG IF NOT EXISTS prod
  COMMENT 'Production data catalog';

-- Create schemas by domain
CREATE SCHEMA IF NOT EXISTS prod.app   COMMENT 'Application backend data';
CREATE SCHEMA IF NOT EXISTS prod.sales COMMENT 'Sales and revenue data';
CREATE SCHEMA IF NOT EXISTS prod.ml    COMMENT 'ML features and agent state';
CREATE SCHEMA IF NOT EXISTS prod.ops   COMMENT 'Operational lookup tables';
```

### Service account credentials

Store credentials in Databricks Secrets — never in notebooks or code:

```bash
# Create a secret scope
databricks secrets create-scope --scope prod-credentials

# Store credentials
databricks secrets put --scope prod-credentials --key postgres-password
databricks secrets put --scope prod-credentials --key kafka-sasl-password
databricks secrets put --scope prod-credentials --key snowflake-password
```

In notebooks:
```python
password = dbutils.secrets.get(scope="prod-credentials", key="postgres-password")
```

### Grant access

```sql
-- Grant a team access to a schema (inherits to all tables)
GRANT USE CATALOG ON CATALOG prod TO `data-engineering-team`;
GRANT USE SCHEMA  ON SCHEMA prod.sales TO `data-engineering-team`;
GRANT SELECT, MODIFY ON ALL TABLES IN SCHEMA prod.sales TO `data-engineering-team`;

-- Read-only access for analysts
GRANT USE CATALOG ON CATALOG prod TO `analytics-team`;
GRANT USE SCHEMA  ON SCHEMA prod.sales TO `analytics-team`;
GRANT SELECT ON ALL TABLES IN SCHEMA prod.sales TO `analytics-team`;

-- Service account for application
GRANT USE CATALOG ON CATALOG prod TO `app-service-account`;
GRANT USE SCHEMA  ON SCHEMA prod.app TO `app-service-account`;
GRANT SELECT, MODIFY ON ALL TABLES IN SCHEMA prod.app TO `app-service-account`;
```

For row-level and column-level controls: [Access Control Review](../trust-foundations/access-control.md).

## Networking checklist

Before migration starts, confirm:

```
[ ] Workspace is in the correct cloud region (same as source data store)
[ ] Private Link or VPC peering configured if source DB is in a private VPC
[ ] Warehouse IP range is allowlisted in source DB security group
[ ] Egress to external Kafka/Kinesis brokers is open (if streaming)
[ ] Corporate network / VPN has access to workspace hostname
[ ] JDBC driver version is compatible (Databricks JDBC 2.7+)
```

Firewall rules for Databricks SQL Warehouse outbound connections typically need to allow port 443 (HTTPS) to the workspace domain and port 443 to cloud storage (S3/ADLS/GCS).

## Warehouse sizing guide

Start at the recommended size; scale up if P95 latency > SLA target after OPTIMIZE + bloom filters are in place.

| Workload characteristics | Starting warehouse size |
| --- | --- |
| < 50 concurrent users, ad-hoc analytics | Small (2 DBU/h) |
| 50–200 concurrent, BI dashboards | Medium (4 DBU/h) |
| 200–500 concurrent, app backend | Large (8 DBU/h) |
| 500–1000 concurrent, point lookups / feature serving | X-Large (16 DBU/h) |
| > 1000 concurrent or streaming writes | 2X-Large (32 DBU/h) |

Multi-cluster warehouses (Pro tier) scale horizontally. Set `min_num_clusters` to 1 and `max_num_clusters` based on peak load. Each cluster adds the base size in capacity.

## Scheduled maintenance jobs

Set up these Databricks Workflow tasks to run weekly:

```python
# OPTIMIZE and VACUUM all production tables
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
w = WorkspaceClient()

schemas = ["prod.app", "prod.sales", "prod.ml", "prod.ops"]

for schema in schemas:
    tables = spark.sql(f"SHOW TABLES IN {schema}").collect()
    for t in tables:
        full_name = f"{schema}.{t['tableName']}"
        try:
            spark.sql(f"OPTIMIZE {full_name}")
            spark.sql(f"VACUUM {full_name} RETAIN 168 HOURS")
            print(f"Maintained: {full_name}")
        except Exception as e:
            print(f"Error on {full_name}: {e}")
```

Run ANALYZE monthly to refresh query optimizer statistics:
```sql
ANALYZE TABLE prod.sales.orders COMPUTE STATISTICS FOR ALL COLUMNS;
```

## Monitoring queries

```sql
-- Daily warehouse utilization (DBU consumption by warehouse)
SELECT
  warehouse_name,
  DATE(usage_date) AS day,
  SUM(usage_quantity) AS dbus,
  SUM(usage_quantity) * 0.22 AS estimated_cost_usd  -- Serverless rate; adjust for Pro
FROM system.billing.usage
WHERE usage_date >= CURRENT_DATE - 30
  AND sku_name LIKE '%SQL%'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Slow queries (> 10s) in the last 24 hours
SELECT
  start_time,
  user_name,
  total_time_ms / 1000 AS duration_sec,
  LEFT(statement_text, 200) AS query_preview
FROM system.query.history
WHERE total_time_ms > 10000
  AND start_time >= NOW() - INTERVAL 24 HOURS
ORDER BY total_time_ms DESC
LIMIT 50;

-- Failed queries
SELECT
  start_time,
  user_name,
  error_message,
  LEFT(statement_text, 200) AS query_preview
FROM system.query.history
WHERE status = 'FAILED'
  AND start_time >= NOW() - INTERVAL 24 HOURS
ORDER BY start_time DESC;
```

## Personal access token management

Rotate tokens on a schedule (recommended: 90 days). Use service principals for production workloads rather than user tokens:

```bash
# Create a service principal
databricks service-principals create --display-name "lakebase-app-backend"

# Generate an OAuth secret for the service principal
databricks service-principals generate-secret <sp-id>
```

For audit: query `system.access.audit` to see token usage.

## Related

- Access control setup: [Access Control Review](../trust-foundations/access-control.md)
- Compliance and data masking: [Compliance & Governance](../trust-foundations/compliance.md)
- Unity Catalog concepts: [Unity Catalog](../databricks-101/unity-catalog.md)
- DBU billing and cost: [DBUs and Billing](../databricks-101/dbus-and-billing.md)
- Troubleshooting connection issues: [Troubleshooting](../troubleshooting.md)
