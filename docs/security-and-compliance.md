# Security & Compliance

How Databricks Lakebase handles data security, access control, regulatory compliance, and audit requirements. This page covers what you need to know before and during a migration engagement.

## Security model overview

```
Unity Catalog
├── Metastore admin (account-level)
│   └── controls: catalogs, metastore config, identity federation
├── Catalog owner
│   └── controls: schemas, catalog-level grants
├── Schema owner
│   └── controls: tables in schema, schema-level grants
└── Table-level grants (SELECT, MODIFY, ALL PRIVILEGES)
    ├── Column masks (row-level visibility of sensitive columns)
    └── Row filters (user-level visibility of specific rows)
```

All access is governed through Unity Catalog. There is no "side door" to Delta tables that bypasses Unity Catalog grants — storage-level access requires explicit catalog permissions.

## Authentication

| Method | Use case |
| --- | --- |
| Personal Access Token (PAT) | Development, interactive queries, BI tools |
| Service Principal + OAuth | Production applications, pipelines, CI/CD |
| SSO / SAML 2.0 | Human users, federated through corporate IdP |
| Azure AD / Entra ID | Azure deployments; native AAD group sync |
| Google Workspace | GCP deployments; Google group federation |

**Recommendation:** Use service principals for all production workloads. Rotate PATs every 90 days. Enforce MFA for human users.

## Column-level security (column masking)

Apply data masking functions to sensitive columns. The mask is enforced at query time — users see masked values without needing a separate masked view:

```sql
-- Step 1: Create a masking policy function
CREATE FUNCTION prod.security.mask_email(email STRING)
RETURNS STRING
RETURN CASE
  WHEN is_account_group_member('data-engineers') THEN email
  ELSE CONCAT(LEFT(email, 2), '***@***.***')
END;

-- Step 2: Apply to a column
ALTER TABLE prod.app.users
  ALTER COLUMN email
  SET MASK prod.security.mask_email;

-- Step 3: Verify (as a non-engineer user)
SELECT email FROM prod.app.users LIMIT 5;
-- Returns: "jo***@***.***"
```

## Row-level security (row filters)

Restrict which rows each user sees based on attributes:

```sql
-- Create a row filter function
CREATE FUNCTION prod.security.region_filter(region STRING)
RETURNS BOOLEAN
RETURN is_account_group_member('global-admin')
    OR current_user() IN (
        SELECT user_email FROM prod.security.region_access
        WHERE allowed_region = region
    );

-- Apply to a table
ALTER TABLE prod.sales.orders
  SET ROW FILTER prod.security.region_filter ON (region);
```

## Audit logging

Unity Catalog logs every access event to `system.access.audit`:

```sql
-- Who accessed a specific table in the last 7 days?
SELECT
  event_time,
  user_identity.email AS user,
  action_name,
  request_params['table_full_name'] AS table_name
FROM system.access.audit
WHERE request_params['table_full_name'] = 'prod.app.users'
  AND event_time >= NOW() - INTERVAL 7 DAYS
ORDER BY event_time DESC;

-- List all users who ran a SELECT on PII-tagged tables
SELECT DISTINCT
  user_identity.email AS user,
  request_params['table_full_name'] AS table_name,
  MIN(event_time) AS first_access,
  MAX(event_time) AS last_access
FROM system.access.audit
WHERE action_name = 'commandSubmit'
  AND request_params['table_full_name'] IN (
    SELECT CONCAT(table_catalog, '.', table_schema, '.', table_name)
    FROM system.information_schema.table_tags
    WHERE tag_name = 'pii' AND tag_value = 'true'
  )
GROUP BY 1, 2
ORDER BY 1, 2;
```

Audit logs are retained for 1 year by default in `system.access.audit`.

## Compliance frameworks

### SOC 2 Type II

Databricks is SOC 2 Type II certified. Your Unity Catalog audit logs and access control configurations are the primary evidence artifacts for a Databricks SOC 2 audit:

- Access logs: `system.access.audit`
- Grant history: query `system.information_schema.table_privileges`
- Change history: Delta Lake transaction log (accessible via `DESCRIBE HISTORY table`)

### GDPR / CCPA (Right to Delete)

```sql
-- Right to delete: remove a user's personal data across all tables
-- Step 1: Identify which tables contain the user's data
SELECT DISTINCT table_name
FROM system.information_schema.column_tags
WHERE tag_name = 'pii' AND tag_value = 'true';

-- Step 2: Delete from each identified table
DELETE FROM prod.app.users WHERE user_id = 'user_to_delete';
DELETE FROM prod.app.orders WHERE user_id = 'user_to_delete';
DELETE FROM prod.ml.user_features WHERE user_id = 'user_to_delete';

-- Step 3: Run VACUUM after deletion to purge from storage (required for GDPR compliance)
-- Note: wait for retention period if time travel audit trails are required
VACUUM prod.app.users RETAIN 0 HOURS;  -- WARNING: disables time travel for this table
```

**GDPR note:** Delta's time travel means deleted rows still exist in old Delta versions until VACUUM runs. If GDPR requires immediate purge of deleted data from storage, run `VACUUM RETAIN 0 HOURS` immediately after deletion. This disables time travel for the affected files.

### HIPAA

For HIPAA workloads:
- Use a dedicated catalog with restricted access (`prod-phi`)
- Apply column masking to all PHI columns (18 HIPAA identifiers)
- Enable audit logging on all tables in the PHI catalog
- Use Unity Catalog row filters to restrict access to authorized users only
- Sign a BAA (Business Associate Agreement) with Databricks

Databricks supports HIPAA-eligible workloads on AWS, Azure, and GCP. Contact your Databricks account team to confirm the BAA and configuration requirements for your region.

### PCI DSS

For workloads that store or process payment card data:
- Isolate in a dedicated catalog with no cross-catalog data flows
- Apply tokenization or masking to PANs (primary account numbers) using column masks
- Enable network isolation (private link) for the workspace
- Document data flows in the Data Inventory

## Encryption

| Layer | How Databricks handles it |
| --- | --- |
| Data in transit | TLS 1.2+ on all connections (JDBC, REST API, storage) |
| Data at rest | AES-256 via cloud provider (S3 SSE, ADLS encryption, GCS CMEK) |
| Customer-managed keys | Supported on all three clouds; requires Enterprise tier |
| Workspace secrets | Stored encrypted in Databricks Secrets; never logged |

## Network isolation options

| Option | When to use |
| --- | --- |
| Default (public endpoint) | Dev/test environments; low-sensitivity data |
| IP allowlist | Restrict workspace access to corporate IP ranges |
| Private Link (Azure) / PrivateLink (AWS) | Production workloads; no public internet exposure |
| VPC peering (AWS) / VNet injection (Azure) | Connect workspace to existing private VPC/VNet |

Private Link setup requires coordination between your cloud platform team and the Databricks account team. Plan 2–4 weeks for provisioning.

## Before migrating PII or regulated data

The [Compliance & Governance Trust Foundation](trust-foundations/compliance.md) must be complete:

```
[ ] PII columns identified and tagged (column_tags with pii = 'true')
[ ] Column masking functions created and applied
[ ] Row filters applied to sensitive tables
[ ] Audit logging verified (test a SELECT; confirm it appears in system.access.audit)
[ ] Data retention policy documented and VACUUM schedule configured
[ ] Right-to-delete procedure tested
[ ] CISO or compliance officer has signed off
```

Do not migrate PII data into Unity Catalog until masking is in place. Once data lands in Lakebase, it is queryable — incomplete masking means unmasked exposure.

## Related

- Access control setup details: [Access Control Review](trust-foundations/access-control.md)
- PII tagging and compliance checklist: [Compliance & Governance](trust-foundations/compliance.md)
- Unity Catalog governance: [Unity Catalog](databricks-101/unity-catalog.md)
- Governed tags for PII classification: [Governed Tags](databricks-101/governed-tags.md)
