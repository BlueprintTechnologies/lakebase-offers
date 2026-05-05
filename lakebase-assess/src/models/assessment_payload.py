"""Pydantic model for the complete assessment payload."""

from typing import Optional

from pydantic import BaseModel, Field

from src.models.concurrency import ConcurrencySignals
from src.models.query_history import QueryHistory
from src.models.security import SecurityPatterns
from src.models.table_metadata import TableMetadataCollection


class AssessmentPayload(BaseModel):
    """Complete data payload from all connectors, ready for scoring."""

    platform: str = Field(description="Source platform name")
    query_history: QueryHistory = Field(default_factory=lambda: QueryHistory(platform=""))
    table_metadata: TableMetadataCollection = Field(default_factory=lambda: TableMetadataCollection(platform=""))
    concurrency_signals: Optional[ConcurrencySignals] = None
    security_patterns: Optional[SecurityPatterns] = None

    # Platform display name from connector
    platform_display_name: str = ""

    # Flags for scoring convenience
    @property
    def has_heavy_udf(self) -> bool:
        return self.query_history.has_heavy_udf

    @property
    def has_stored_procs(self) -> bool:
        return self.query_history.has_stored_procs

    @property
    def has_real_time(self) -> bool:
        return self.query_history.has_real_time_queries

    @property
    def is_customer_facing(self) -> bool:
        return self.query_history.has_customer_facing

    @property
    def has_pii_sensitive_data(self) -> bool:
        return self.table_metadata.has_sensitive_tables

    @property
    def needs_scaling(self) -> bool:
        if self.concurrency_signals:
            return self.concurrency_signals.needs_scaling
        return False

    @property
    def has_security_issues(self) -> bool:
        if self.security_patterns:
            return self.security_patterns.needs_security_hardening
        return False

    @property
    def total_tables(self) -> int:
        return len(self.table_metadata.tables)

    @property
    def total_queries(self) -> int:
        return len(self.query_history.queries)

    @property
    def has_timeouts(self) -> bool:
        return self.query_history.has_timeouts

    @property
    def has_errors(self) -> bool:
        return self.query_history.has_errors
