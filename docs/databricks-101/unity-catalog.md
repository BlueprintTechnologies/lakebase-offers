# Unity Catalog

Unity Catalog is Databricks' unified governance layer. It is the single place where access control, data lineage, and metadata live for everything in your Databricks workspace — tables, files, ML models, notebooks, and dashboards.

## Why it matters for migration

When you migrate a workload to Lakebase, you do not just move data — you also move the access model, ownership, and compliance posture. Unity Catalog is where all of that lives after migration.

If your current platform has a complex access model (role hierarchies, row-level security, column masking), Unity Catalog replicates and consolidates it. If your current platform has minimal governance, Unity Catalog is the opportunity to establish it properly from day one.

## The three-level namespace

Unity Catalog organizes data into a three-level hierarchy:

```
Catalog
  └── Schema
        └── Table / View / Volume / Function
```

| Level | Analogous to | Example |
| --- | --- | --- |
| **Catalog** | Snowflake database / Oracle instance | `prod`, `dev`, `analytics` |
| **Schema** | Snowflake schema / Oracle schema | `sales`, `finance`, `hr` |
| **Table / View** | Table in any platform | `orders`, `customer_profiles` |

You reference objects with three-part names: `catalog.schema.table`.

```sql
SELECT * FROM prod.sales.orders WHERE created_at >= '2026-01-01';
```

## Access control in Unity Catalog

### Granting access

Access is granted to principals (users, groups, or service accounts) on objects at any level of the hierarchy:

```sql
-- Grant SELECT on a specific table
GRANT SELECT ON TABLE prod.sales.orders TO `analysts`;

-- Grant access to all tables in a schema
GRANT SELECT ON ALL TABLES IN SCHEMA prod.sales TO `sales-team`;

-- Grant access to a catalog (all schemas and tables within)
GRANT USE CATALOG ON CATALOG prod TO `data-platform-team`;
```

### Column-level masking

```sql
-- Create a masking function
CREATE FUNCTION prod.security.mask_email(email STRING)
  RETURNS STRING
  RETURN IF(is_account_group_member('pii-viewers'), email, '****@****.com');

-- Apply to a column
ALTER TABLE prod.sales.customers
  ALTER COLUMN email SET MASK prod.security.mask_email;
```

### Row-level filtering

```sql
-- Create a row filter
CREATE FUNCTION prod.security.region_filter(region STRING)
  RETURNS BOOLEAN
  RETURN is_account_group_member('global-access') OR current_user_region() = region;

-- Apply to a table
ALTER TABLE prod.sales.orders
  SET ROW FILTER prod.security.region_filter ON (region);
```

## Data lineage

Unity Catalog automatically tracks which tables read from which other tables. This lineage is captured through SQL query history — you do not need to annotate anything.

To view lineage for a table:

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
lineage = w.table_lineage.list("prod.sales.orders")
for item in lineage:
    print(item)
```

Or in the Databricks UI: Catalog Explorer → select a table → Lineage tab.

## System tables

Unity Catalog exposes audit and usage data through `system.*` tables. These power the assessor's post-migration monitoring:

| Table | What it contains |
| --- | --- |
| `system.access.audit` | All access and query events |
| `system.billing.usage` | DBU consumption by resource |
| `system.query.history` | Every SQL query (with runtime, status, warehouse) |
| `system.information_schema.tables` | All registered tables with metadata |
| `system.information_schema.columns` | Column-level metadata |

```sql
-- Who has accessed a specific table in the last 7 days?
SELECT timestamp, user_identity.email, action_name
FROM system.access.audit
WHERE request_params.tableFullName = 'prod.sales.orders'
  AND timestamp >= NOW() - INTERVAL 7 DAYS
ORDER BY timestamp DESC;
```

## Unity Catalog vs. Hive metastore

Older Databricks workspaces use the Hive metastore. Unity Catalog is the modern replacement. Key differences:

| Feature | Hive Metastore | Unity Catalog |
| --- | --- | --- |
| Namespace | 2-level (schema.table) | 3-level (catalog.schema.table) |
| Access control | Workspace-level RBAC | Fine-grained: table, column, row |
| Data lineage | Not built-in | Automatic |
| Cross-workspace sharing | Manual | Native (Delta Sharing) |
| Column masking | Not supported | Native |
| Row filtering | Not supported | Native |

If your Databricks workspace is on Hive metastore, migrating to Unity Catalog is a prerequisite for the Lakebase migration. Blueprint can scope this as a pre-work sprint.

## Related

- Masking and compliance: [Compliance & Governance](../trust-foundations/compliance.md)
- Governing tags: [Governed Tags](governed-tags.md)
- Access control setup: [Access Control Review](../trust-foundations/access-control.md)
- Databricks Unity Catalog docs: [docs.databricks.com/en/data-governance/unity-catalog](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
