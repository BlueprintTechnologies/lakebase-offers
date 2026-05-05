# Data Inventory & Schema Documentation

Document what you have before you move it. Migrations that skip this step discover undocumented tables, orphaned schemas, and unknown owners mid-sprint — the most expensive time to find them.

## What this foundation closes

- Missing table and column descriptions in Unity Catalog
- Unknown data owners for tables in scope
- Undocumented relationships (implicit foreign keys, derived tables)
- Orphaned or deprecated tables accidentally included in migration scope

## The inventory checklist

Work through this list for each workload in your PoC scope:

### Tables

- [ ] Every table has a description in Unity Catalog (even one sentence)
- [ ] Every table has a designated owner (team or named individual)
- [ ] Every table's row count, size, and last-updated timestamp is known
- [ ] Partitioning scheme is documented (partition column, partition range)
- [ ] Tables planned for retirement are flagged and excluded from migration scope

### Columns

- [ ] Every column has a data type and a description
- [ ] PII or sensitive columns are tagged (email, ssn, phone, dob, etc.)
- [ ] Nullable vs. NOT NULL behavior is documented
- [ ] Business-name aliases are documented (e.g., `cust_id` = customer primary key)

### Relationships

- [ ] Primary keys are declared or noted
- [ ] Foreign key relationships are documented (even if not enforced)
- [ ] Implicit joins (join patterns found in query history but not declared as constraints) are captured

### Data flows

- [ ] Source systems writing to these tables are identified
- [ ] Downstream consumers (dashboards, pipelines, APIs) are listed
- [ ] Refresh frequency and SLA are documented

## How to do this in Databricks Unity Catalog

### Add a table description

```sql
COMMENT ON TABLE catalog.schema.my_table IS
  'Customer transaction history. Source: Salesforce CRM. Owner: data-platform@company.com. Refreshed hourly.';
```

### Add column descriptions

```sql
ALTER TABLE catalog.schema.my_table ALTER COLUMN customer_id COMMENT 'Primary key. Matches CRM account ID.';
ALTER TABLE catalog.schema.my_table ALTER COLUMN email COMMENT 'Customer email. PII — masked for non-privileged users.';
```

### Tag PII columns

```sql
ALTER TABLE catalog.schema.my_table SET TAGS ('pii' = 'true', 'pii_type' = 'email');
ALTER TABLE catalog.schema.my_table ALTER COLUMN email SET TAGS ('pii' = 'true', 'pii_type' = 'email');
```

### Declare a primary key (informational constraint)

```sql
ALTER TABLE catalog.schema.my_table ADD CONSTRAINT pk_customer_id PRIMARY KEY (customer_id);
```

### Declare a foreign key

```sql
ALTER TABLE catalog.schema.orders
  ADD CONSTRAINT fk_customer
  FOREIGN KEY (customer_id) REFERENCES catalog.schema.customers(customer_id);
```

## Prioritization

You do not need to document every table in your platform before the PoC. Focus on:

1. **Tables used by Priority 1 workloads** — these are the migration scope
2. **High-traffic tables** (top 20 by query volume from the assessor output)
3. **PII-flagged tables** (compliance requirement before migration)

The full estate can be documented incrementally after the PoC.

## Shortcut: AI-generated descriptions

If you have many undocumented tables, Databricks AI can generate first-pass descriptions from column names and sample data using `COMMENT ON TABLE ... IS AI_GENERATE_DESCRIPTION()`. Human review is still required, but AI generation dramatically reduces the time investment for large schemas.

## Related

- Declaring keys: part of [SQL Compatibility Check](sql-compatibility.md)
- Tagging for compliance: [Compliance & Governance](compliance.md)
- After migration: keep documentation updated through [Governed Tags](../databricks-101/governed-tags.md)
