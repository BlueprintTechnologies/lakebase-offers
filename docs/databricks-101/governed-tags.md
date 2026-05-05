# Governed Tags

Governed tags are Unity Catalog's mechanism for classifying and organizing tables, schemas, and columns with structured metadata. They are how Databricks tracks data ownership, domain, PII status, and any other classification you need.

## What governed tags do

A governed tag is a key-value pair attached to a Unity Catalog object. Unlike free-text comments (which are unstructured), governed tags are validated against a controlled vocabulary — you define the allowed keys and values centrally, and Unity Catalog enforces them.

**Example:**
```
Key: domain        Allowed values: finance, sales, hr, supply-chain, marketing
Key: pii           Allowed values: true, false
Key: classification Allowed values: public, internal, confidential, restricted
Key: sla_tier      Allowed values: gold, silver, bronze
```

Tags are searchable, auditable, and can trigger policy enforcement (access control, data masking) when combined with Unity Catalog's attribute-based access features.

## Why tags matter for your migration

Your assessment report uses three tag types:

1. **Domain tags** — which business domain owns this table (used for the domain breakdown in your scorecard)
2. **PII tags** — which tables and columns contain personal data (required for the compliance checklist)
3. **Classification tags** — how sensitive this data is (informs access control setup)

Tables without domain tags appear as "Unassigned" in the scorecard breakdown. If you have a large "Unassigned" slice, tagging is a Trust Foundations priority before Phase 2.

## Creating a governed tag policy

### Step 1: Define the tag keys and allowed values

```sql
-- Create a governed tag (in the Unity Catalog metastore admin)
CREATE TAG catalog_name.information_schema.domain
  COMMENT 'Business domain that owns this data asset'
  ALLOWED VALUES ('finance', 'sales', 'hr', 'supply-chain', 'marketing', 'platform', 'shared');

CREATE TAG catalog_name.information_schema.pii
  COMMENT 'Whether this asset contains personally identifiable information'
  ALLOWED VALUES ('true', 'false');

CREATE TAG catalog_name.information_schema.classification
  COMMENT 'Data sensitivity classification'
  ALLOWED VALUES ('public', 'internal', 'confidential', 'restricted');
```

### Step 2: Apply tags to tables and schemas

```sql
-- Tag a schema (all tables inherit unless overridden)
ALTER SCHEMA prod.finance
  SET TAGS ('domain' = 'finance', 'classification' = 'confidential');

-- Tag a specific table
ALTER TABLE prod.finance.payroll
  SET TAGS ('domain' = 'finance', 'pii' = 'true', 'classification' = 'restricted');

-- Tag a specific column
ALTER TABLE prod.sales.customers
  ALTER COLUMN ssn
  SET TAGS ('pii' = 'true', 'pii_type' = 'ssn');
```

### Step 3: Query tags programmatically

```sql
-- Find all tables tagged as PII
SELECT table_catalog, table_schema, table_name, tag_value
FROM system.information_schema.table_tags
WHERE tag_name = 'pii' AND tag_value = 'true'
ORDER BY table_catalog, table_schema, table_name;

-- Find all tables in the 'finance' domain
SELECT table_catalog, table_schema, table_name
FROM system.information_schema.table_tags
WHERE tag_name = 'domain' AND tag_value = 'finance';

-- Find all PII columns across the estate
SELECT table_catalog, table_schema, table_name, column_name, tag_value
FROM system.information_schema.column_tags
WHERE tag_name = 'pii' AND tag_value = 'true'
ORDER BY table_catalog, table_schema, table_name, column_name;
```

## Tagging strategy for migrations

You do not need to tag every table before migration. A practical approach:

**Before Phase 1 PoC (required):**
- Tag tables in PoC scope with `domain` and `pii` (enables assessor domain breakdown and compliance checklist)

**Before Phase 2 (recommended):**
- Tag all tables in migration scope with `domain`, `classification`, and `pii`
- Apply `sla_tier` to production tables that have SLA requirements

**Ongoing (best practice):**
- Require tag application as part of any new table creation process
- Review "Unassigned" tables monthly and close the gap

## Bulk tagging with AI assistance

For large schemas (100+ tables), manual tagging is impractical. Databricks AI can suggest tags based on column names, table names, and sample data:

```python
from databricks.sdk import WorkspaceClient
import anthropic

w = WorkspaceClient()
client = anthropic.Anthropic()

# Get list of untagged tables
untagged = w.tables.list(catalog_name="prod", schema_name="sales")

for table in untagged:
    # Use AI to suggest domain and classification
    columns = [col.name for col in table.columns]
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"Table '{table.name}' has columns: {columns}. "
                      f"Suggest: domain (finance/sales/hr/supply-chain/platform), "
                      f"pii (true/false), classification (public/internal/confidential/restricted). "
                      f"Reply as JSON only."
        }]
    )
    # Review and apply suggestions
    print(f"{table.name}: {response.content[0].text}")
```

AI suggestions require human review before application. This workflow reduces tagging time for large schemas from weeks to days.

## Related

- PII tagging as a trust foundation: [Compliance & Governance](../trust-foundations/compliance.md)
- Using tags in access control: [Access Control Review](../trust-foundations/access-control.md)
- Unity Catalog overview: [Unity Catalog](unity-catalog.md)
- Databricks governed tags docs: [docs.databricks.com/en/data-governance/unity-catalog/governed-tags](https://docs.databricks.com/en/data-governance/unity-catalog/governed-tags.html)
