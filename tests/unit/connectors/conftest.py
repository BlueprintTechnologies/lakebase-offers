"""Shared fixtures with realistic sample data for connector integration tests."""

import pytest


# Realistic Snowflake query history rows (what the API would return)
SAMPLE_SNOWFLAKE_QUERY_ROWS = [
    (
        "q001",
        "SELECT * FROM orders WHERE customer_id = 12345",
        "PROD_DB",
        "PUBLIC",
        "SELECT",
        2500,
        1,
        5242880,
        1,
        0,
        "SUCCESS",
        "2026-04-01T10:00:00",
        "2026-04-01T10:00:02",
        False,
        False,
        42,
    ),
    (
        "q002",
        "SELECT SUM(amount) FROM orders GROUP BY region",
        "PROD_DB",
        "PUBLIC",
        "SELECT",
        45000,
        50,
        104857600,
        3,
        0,
        "SUCCESS",
        "2026-04-01T11:00:00",
        "2026-04-01T11:00:45",
        False,
        False,
        43,
    ),
    (
        "q003",
        "INSERT INTO staging_loads VALUES ('a','b','c')",
        "PROD_DB",
        "PUBLIC",
        "INSERT",
        50,
        1,
        1024,
        1,
        0,
        "SUCCESS",
        "2026-04-02T08:00:00",
        "2026-04-02T08:00:00",
        False,
        False,
        44,
    ),
]

SNOWFLAKE_QUERY_COLUMNS = [
    "QUERY_ID", "QUERY_TEXT", "DATABASE_NAME", "SCHEMA_NAME", "QUERY_TYPE",
    "TOTAL_ELAPSED_TIME", "ROWS_PRODUCED", "BYTES_SCANNED",
    "CONCURRENT_CONCURRENCY", "QUERY_FAILURES", "QUERY_STATUS",
    "START_TIME", "END_TIME", "IS_CLIENT_QUERY_AGENT_REPORTING",
    "HAS_OUT_PUT_PARAMS", "SESSION_ID",
]

# Realistic Snowflake table metadata rows
SAMPLE_SNOWFLAKE_TABLE_ROWS = [
    ("ANALYTICS", "PUBLIC", "orders", "TABLE", 50000000, 21474836480, "2026-04-01T00:00:00", "N"),
    ("ANALYTICS", "PUBLIC", "customers", "TABLE", 5000000, 1073741824, "2026-03-01T00:00:00", "N"),
    ("RAW", "PUBLIC", "event_stream", "TABLE", 200000000, 107374182400, None, "N"),
    ("ANALYTICS", "PUBLIC", "daily_rollup", "TABLE", 1000, 4096, "2026-05-05T00:00:00", "N"),
]

# Realistic Snowflake cost rows
SAMPLE_SNOWFLAKE_COST_ROWS = [(150.5, 152.3)]

# Realistic Snowflake concurrency rows
SAMPLE_SNOWFLAKE_CONCURRENCY_ROWS = [
    ("2026-04-01T10:00:00", 5000000, 2000000, 1000000, 10, 100, 45, 12, 3, 0.6, 0.4),
    ("2026-04-01T11:00:00", 7000000, 3000000, 2000000, 12, 120, 62, 15, 5, 0.7, 0.5),
    ("2026-04-01T12:00:00", 4000000, 1500000, 500000, 8, 90, 35, 8, 1, 0.5, 0.3),
]


# Realistic Postgres table metadata rows (pg_stat_user_tables)
SAMPLE_POSTGRES_TABLE_ROWS = [
    ("public", "orders", "app_user", 536870912, 10000000, "2026-04-01 10:00:00", False),
    ("public", "users", "app_user", 104857600, 500000, "2026-05-01 08:00:00", False),
    ("public", "audit_log", "app_user", 2147483648, 50000000, None, False),
]

POSTGRES_TABLE_COLUMNS = [
    "schemaname", "tablename", "tableowner", "table_size_bytes",
    "row_count", "last_analyze", "is_partition_table",
]


# Realistic BigQuery table metadata rows
SAMPLE_BIGQUERY_TABLE_ROWS = [
    ("prod_dataset", "orders", "TABLE", 50000000, 21474836480, True, "created_at"),
    ("prod_dataset", "customers", "TABLE", 5000000, 1073741824, False, None),
]


# Realistic MySQL table metadata rows
SAMPLE_MYSQL_TABLE_ROWS = [
    ("production", "orders", "BASE TABLE", 30000000, 1610612736, "InnoDB", "2026-04-01 10:00:00"),
    ("production", "customers", "BASE TABLE", 2000000, 107374182, "InnoDB", "2026-05-01 08:00:00"),
]


@pytest.fixture
def snowflake_query_rows():
    """Sample Snowflake query history rows."""
    return SAMPLE_SNOWFLAKE_QUERY_ROWS


@pytest.fixture
def snowflake_query_columns():
    """Column names for Snowflake query history rows."""
    return SNOWFLAKE_QUERY_COLUMNS


@pytest.fixture
def snowflake_table_rows():
    """Sample Snowflake table metadata rows."""
    return SAMPLE_SNOWFLAKE_TABLE_ROWS


@pytest.fixture
def snowflake_cost_rows():
    """Sample Snowflake cost rows."""
    return SAMPLE_SNOWFLAKE_COST_ROWS


@pytest.fixture
def postgres_table_rows():
    """Sample Postgres table metadata rows."""
    return SAMPLE_POSTGRES_TABLE_ROWS


@pytest.fixture
def mysql_table_rows():
    """Sample MySQL table metadata rows."""
    return SAMPLE_MYSQL_TABLE_ROWS
