# Access Control Review

Replicate the access model from your source platform to Unity Catalog before migration. Access gaps discovered post-cutover cause incidents and erode trust in the migration program.

## What this foundation closes

- Users or teams blocked from data they previously had access to
- Over-privileged accounts that violate least-privilege principles
- Ungoverned service accounts with broader access than needed
- Access patterns that relied on implicit grants or legacy role structures

## The access control checklist

### Users and groups

- [ ] All source platform users are mapped to Databricks workspace users or groups
- [ ] Group hierarchy mirrors the source (or is simplified to fewer, broader groups)
- [ ] SSO/SCIM provisioning is configured so Databricks groups stay in sync with IdP
- [ ] External users (contractors, partners) are provisioned with appropriate expiry

### Table-level grants

- [ ] Every table in migration scope has explicit Unity Catalog grants defined
- [ ] Grants are on groups, not individual users (except for the table owner)
- [ ] `SELECT` is granted only where the source had `SELECT`
- [ ] `MODIFY` (INSERT, UPDATE, DELETE) is granted only to service accounts that write to the table

### Column-level controls

- [ ] PII columns have column masks configured before any production data is loaded
- [ ] Sensitive columns (salary, SSN, health data) are masked for non-privileged roles
- [ ] Masking policy is tested with a non-privileged account before cutover

### Row-level controls

- [ ] Row filters are configured where the source had row-level security
- [ ] Dynamic view logic is replicated as Unity Catalog row filters
- [ ] Filters are tested with a non-privileged account before cutover

### Service accounts

- [ ] Every pipeline service account has a named owner (human or team)
- [ ] Service account grants are scoped to the minimum required (`SELECT` for readers, `MODIFY` for writers)
- [ ] No service account has `OWNER` or `ALL PRIVILEGES` unless required
- [ ] Service account credentials are rotated to new secrets (not copied from source)

## How to replicate grants in Unity Catalog

### Grant SELECT to a group

```sql
GRANT SELECT ON TABLE catalog.schema.my_table TO `data-analysts`;
GRANT SELECT ON TABLE catalog.schema.my_table TO `service-account-reporting@company.com`;
```

### Grant table ownership

```sql
ALTER TABLE catalog.schema.my_table OWNER TO `data-platform-team`;
```

### Create a column mask for PII

```sql
-- First, create a masking function
CREATE OR REPLACE FUNCTION catalog.schema.mask_email(email STRING)
  RETURNS STRING
  RETURN CASE
    WHEN is_account_group_member('pii-access') THEN email
    ELSE CONCAT(LEFT(email, 2), '****@****.com')
  END;

-- Apply to column
ALTER TABLE catalog.schema.customers
  ALTER COLUMN email
  SET MASK catalog.schema.mask_email;
```

### Create a row filter

```sql
-- Filter rows to only the user's region
CREATE OR REPLACE FUNCTION catalog.schema.filter_by_region(region_col STRING)
  RETURNS BOOLEAN
  RETURN is_account_group_member('global-access')
    OR current_user_region() = region_col;

ALTER TABLE catalog.schema.sales_data
  SET ROW FILTER catalog.schema.filter_by_region ON (region);
```

## Auditing the source platform

Before building Unity Catalog grants, export the source platform's access model:

### Snowflake

```sql
SELECT grantee_name, privilege, granted_on, name
FROM snowflake.account_usage.grants_to_roles
WHERE granted_on = 'TABLE'
  AND name ILIKE '%your_schema%'
ORDER BY grantee_name, name;
```

### BigQuery

```bash
bq show --format=prettyjson project:dataset.table | jq '.access'
```

### Redshift

```sql
SELECT u.usename, t.schemaname, t.tablename, has_table_privilege(u.usename, t.tablename, 'SELECT') AS can_select
FROM pg_user u
CROSS JOIN pg_tables t
WHERE t.schemaname = 'your_schema'
ORDER BY u.usename, t.tablename;
```

## Common pitfalls

**Role explosion.** Source platforms often have dozens of fine-grained roles that map to 3–4 Unity Catalog groups in practice. Simplify during migration — fewer, broader groups are easier to govern and audit.

**Implicit grants.** If the source platform granted `PUBLIC` access to some tables (all authenticated users can read), replicate this explicitly in Unity Catalog with a grant to `account users`.

**Service account sprawl.** Migrations are a good time to retire service accounts that no longer correspond to active pipelines. Audit the source for service accounts that have not run a query in 90 days — if they are not needed, do not migrate them.

## Testing access before cutover

Before cutting over production traffic, run a validation sweep:

1. Log in as a non-privileged user and verify you can query the tables your role should access
2. Verify you cannot query tables your role should NOT access
3. Verify column masks are applied (check that `email` appears masked for the test user)
4. Verify row filters work (check that the test user only sees their region's data)
5. Test service account tokens against the new Lakebase endpoint before decommissioning the source

## Related

- PII tagging prerequisite: [Data Inventory & Schema Docs](data-inventory.md)
- Column masks and row filters: [Compliance & Governance](compliance.md)
- Unity Catalog model: [Unity Catalog](../databricks-101/unity-catalog.md)
