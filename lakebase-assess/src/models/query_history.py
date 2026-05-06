"""Pydantic models for query history data."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# PII patterns to detect and mask
PII_PATTERNS = [
    r"(?i)\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",  # SSN
    r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
    r"(?i)\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d{1,5})?\b",  # IP
    r"(?i)\b\d{16}\b",  # credit card
    r"(?i)password\s*=\s*\S+",  # password assignments
    r"(?i)api[_-]?key\s*=\s*\S+",  # API keys
    r"(?i)secret\s*=\s*\S+",  # secrets
]


class QueryRecord(BaseModel):
    """A single query execution record from the source platform."""

    query_id: str = Field(description="Unique identifier for the query")
    database: str = Field(description="Target database name")
    schema_name: str = Field(description="Target schema name")
    table_names: list[str] = Field(default=[], description="Tables referenced by this query")
    query_text_fingerprint: str = Field(
        description="Hashed or truncated query fingerprint (never raw PII)"
    )
    query_type: str = Field(description="SELECT|INSERT|UPDATE|DELETE|DDL|DML|OTHER")
    avg_exec_time_ms: Optional[float] = Field(default=None, description="Average execution time in ms")
    min_exec_time_ms: Optional[float] = Field(default=None, description="Minimum execution time in ms")
    max_exec_time_ms: Optional[float] = Field(default=None, description="Maximum execution time in ms")
    total_executions: int = Field(default=1, description="Total number of times this pattern executed")
    avg_rows_returned: Optional[float] = Field(default=None)
    avg_bytes_scanned: Optional[float] = Field(default=None)
    last_executed: Optional[datetime] = Field(default=None)
    first_executed: Optional[datetime] = Field(default=None)
    has_udf: bool = False
    has_stored_procedure: bool = False
    is_real_time: bool = False
    is_customer_facing: bool = False
    timeout_count: int = Field(default=0)
    error_count: int = Field(default=0)

    # New fields for enhanced analysis
    hour_of_day_histogram: list[int] = Field(default=[], description="24-element list, query count per hour")
    is_point_lookup: bool = False  # WHERE primary_key = ?
    is_full_scan: bool = False  # reads > 50% of table rows
    is_write: bool = False  # INSERT/UPDATE/DELETE/MERGE
    cache_hit: bool = False  # did this hit a result cache?
    user_type: str = Field(default="", description="app_service_account | analyst | etl_job | admin")

    @field_validator("query_text_fingerprint")
    @classmethod
    def strip_pii(cls, v: str) -> str:
        """Strip PII patterns from the fingerprint."""
        for pattern in PII_PATTERNS:
            v = re.sub(pattern, "[REDACTED]", v)
        # Truncate to prevent unbounded input
        return v[:500] if len(v) > 500 else v


class QueryHistory(BaseModel):
    """Collection of query records with summary statistics."""

    platform: str = Field(description="Source platform name")
    queries: list[QueryRecord] = Field(default=[])
    total_queries_fetched: int = 0
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    unique_databases: list[str] = []
    unique_tables: list[str] = []
    avg_concurrency: float = 0.0
    peak_concurrency: int = 0

    @property
    def has_heavy_udf(self) -> bool:
        return any(q.has_udf for q in self.queries)

    @property
    def has_stored_procs(self) -> bool:
        return any(q.has_stored_procedure for q in self.queries)

    @property
    def has_real_time_queries(self) -> bool:
        return any(q.is_real_time for q in self.queries)

    @property
    def has_customer_facing(self) -> bool:
        return any(q.is_customer_facing for q in self.queries)

    @property
    def has_timeouts(self) -> bool:
        return any(q.timeout_count > 0 for q in self.queries)

    @property
    def has_errors(self) -> bool:
        return any(q.error_count > 0 for q in self.queries)
