"""Pydantic models for table metadata."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ColumnSpec(BaseModel):
    """Individual column definition."""

    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    distinct_count: Optional[int] = None
    null_count: Optional[int] = None
    avg_row_size_bytes: Optional[float] = None


class TableMetadata(BaseModel):
    """Metadata for a single table in the source platform."""

    database: str = Field(description="Database name")
    schema_name: str = Field(description="Schema name")
    table_name: str = Field(description="Table name")
    table_type: str = Field(description="TABLE|VIEW|MATERIALIZED_VIEW|EXTERNAL")
    row_count: Optional[int] = Field(default=None)
    storage_size_bytes: Optional[int] = Field(default=None)
    is_partitioned: bool = False
    partition_column: Optional[str] = None
    is_clustering_key: bool = False
    clustering_columns: list[str] = Field(default=[])
    column_count: int = 0
    columns: list[ColumnSpec] = Field(default=[])
    last_analyzed: Optional[datetime] = None
    is_stale_stats: bool = False
    join_complexity: int = Field(default=0, description="Avg join depth in queries referencing this table")
    is_frequently_joined: bool = False
    avg_query_count: float = Field(default=0.0, description="Avg daily queries referencing this table")
    data_freshness_hours: Optional[float] = Field(default=None)
    is_sensitive: bool = False
    tags: list[str] = Field(default=[])

    # Data growth rate (item 7a)
    row_count_30d_ago: Optional[int] = Field(default=None, description="from query history or stats")
    monthly_growth_rate_pct: Optional[float] = Field(default=None, description="derived")
    is_fast_growing: bool = Field(default=False, description="> 20% month-over-month")


class TableMetadataCollection(BaseModel):
    """Collection of table metadata across databases."""

    platform: str
    tables: list[TableMetadata] = Field(default=[])
    total_tables_fetched: int = 0
    total_row_count: Optional[int] = None
    total_storage_bytes: Optional[int] = None
    database_count: int = 0
    schema_count: int = 0

    @property
    def has_large_tables(self) -> bool:
        return any(t.row_count and t.row_count > 10_000_000 for t in self.tables)

    @property
    def has_sensitive_tables(self) -> bool:
        return any(t.is_sensitive for t in self.tables)

    @property
    def has_materialized_views(self) -> bool:
        return any(t.table_type == "MATERIALIZED_VIEW" for t in self.tables)
