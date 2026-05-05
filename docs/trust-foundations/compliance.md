# Compliance & Governance

Resolve compliance requirements before the migration sprint, not during it. A compliance gate discovered on migration day blocks cutover and burns PoC time.

## What this foundation closes

- PII and sensitive data without masking configured
- Tables requiring compliance review before platform change
- Audit trail gaps (no lineage, no access logging)
- Retention and deletion requirements not mapped to Delta capabilities

## The compliance checklist

### Data classification

- [ ] All tables in migration scope are classified by data type (public, internal, confidential, restricted)
- [ ] PII columns are identified and tagged in Unity Catalog
- [ ] PHI columns (if applicable) are identified and tagged
- [ ] Financial data (SOX-relevant) is identified and tagged
- [ ] Column masks are configured for all PII/PHI columns before data load

### Regulatory requirements

- [ ] HIPAA: BAA is in place with Databricks (if applicable)
- [ ] PCI-DSS: Confirm Databricks region is in-scope PCI environment (if applicable)
- [ ] SOX: Data lineage and access logging are enabled
- [ ] GDPR/CCPA: Right-to-delete workflow is documented for Delta
- [ ] Internal data policy: Platform change has been approved by the data stewardship process

### Audit trail

- [ ] Databricks audit logging is enabled for the workspace
- [ ] Unity Catalog access logging is turned on
- [ ] Log delivery is configured to your SIEM or data lake
- [ ] Audit log retention meets your policy requirements (typically 1–7 years)

### Data retention and deletion

- [ ] Retention periods are documented for each table
- [ ] Delta time travel retention is configured to match (default: 7 days; extend if needed)
- [ ] Right-to-delete procedure for GDPR/CCPA is documented and tested

## Configuring PII masking in Unity Catalog

### Step 1: Tag the column

```sql
-- Tag at the table level
ALTER TABLE catalog.schema.customers
  SET TAGS ('data_classification' = 'pii');

-- Tag at the column level
ALTER TABLE catalog.schema.customers
  ALTER COLUMN email
  SET TAGS ('pii_type' = 'email_address', 'pii' = 'true');
```

### Step 2: Create a masking function

```sql
-- Email masking: show first 2 chars, mask the rest
CREATE OR REPLACE FUNCTION catalog.schema.mask_email(email STRING)
  RETURNS STRING
  RETURN CASE
    WHEN is_account_group_member('pii-data-access') THEN email
    ELSE REGEXP_REPLACE(email, '(?<=.{2}).(?=.*@)', '*')
  END;

-- SSN masking: show last 4 only
CREATE OR REPLACE FUNCTION catalog.schema.mask_ssn(ssn STRING)
  RETURNS STRING
  RETURN CASE
    WHEN is_account_group_member('hr-data-access') THEN ssn
    ELSE CONCAT('***-**-', RIGHT(ssn, 4))
  END;

-- Complete redaction for high-sensitivity columns
CREATE OR REPLACE FUNCTION catalog.schema.redact(col STRING)
  RETURNS STRING
  RETURN CASE
    WHEN is_account_group_member('restricted-data-access') THEN col
    ELSE '[REDACTED]'
  END;
```

### Step 3: Apply the mask

```sql
ALTER TABLE catalog.schema.customers
  ALTER COLUMN email
  SET MASK catalog.schema.mask_email;

ALTER TABLE catalog.schema.customers
  ALTER COLUMN ssn
  SET MASK catalog.schema.mask_ssn;
```

### Step 4: Test the mask

```sql
-- Run as a non-privileged user; should see masked values
SELECT customer_id, email, ssn FROM catalog.schema.customers LIMIT 5;

-- Run as a privileged user (pii-data-access group); should see real values
-- (grant yourself to the group temporarily to verify, then remove)
```

## Configuring audit logging

### Enable workspace audit logs (workspace admin)

Workspace audit logs are enabled in the Databricks account console → Settings → Audit Logs. Deliver logs to your cloud storage bucket (S3, ADLS, GCS).

### Query audit logs in Databricks

```sql
-- Who queried a specific table in the last 7 days?
SELECT
  timestamp,
  user_identity.email AS user,
  action_name,
  request_params.tableFullName AS table_name
FROM system.access.audit
WHERE request_params.tableFullName = 'catalog.schema.customers'
  AND timestamp >= NOW() - INTERVAL 7 DAYS
ORDER BY timestamp DESC;

-- What tables has a specific user accessed?
SELECT
  timestamp,
  action_name,
  request_params.tableFullName AS table_name
FROM system.access.audit
WHERE user_identity.email = 'analyst@company.com'
  AND timestamp >= NOW() - INTERVAL 30 DAYS
ORDER BY timestamp DESC;
```

## Configuring data retention

### Set Delta table retention (time travel)

```sql
-- Retain 90 days of table history (vs. default 7 days)
ALTER TABLE catalog.schema.customers
  SET TBLPROPERTIES ('delta.logRetentionDuration' = 'interval 90 days');
```

### Implementing right-to-delete (GDPR/CCPA)

```sql
-- Delete a customer's PII from all tables
DELETE FROM catalog.schema.customers WHERE customer_id = 'cust_12345';
DELETE FROM catalog.schema.orders WHERE customer_id = 'cust_12345';
DELETE FROM catalog.schema.events WHERE customer_id = 'cust_12345';

-- VACUUM to physically remove deleted rows from storage (after retention period)
VACUUM catalog.schema.customers RETAIN 0 HOURS;
```

> **Note:** VACUUM with 0 hours retention disables time travel for deleted rows. Balance deletion requirements against time-travel needs in your policy.

## What to send your compliance team

A typical compliance review packet for a Lakebase migration:

1. List of tables being migrated, with their data classification tags
2. Column mask configurations for all PII/PHI columns
3. Access grant list (who can read what after migration)
4. Audit log configuration and delivery destination
5. Databricks compliance certifications relevant to your requirements (from [trust.databricks.com](https://trust.databricks.com))
6. Data processing addendum / BAA if applicable

## Related

- Access model setup: [Access Control Review](access-control.md)
- PII tagging: [Data Inventory & Schema Docs](data-inventory.md)
- Security overview: [Security and Compliance](../security-and-compliance.md)
- Unity Catalog features: [Unity Catalog](../databricks-101/unity-catalog.md)
