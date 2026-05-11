"""Pydantic model for the complete assessment payload."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.concurrency import ConcurrencySignals
from src.models.cost_signals import CostSignals
from src.models.query_history import QueryHistory
from src.models.security import SecurityPatterns
from src.models.table_metadata import TableMetadataCollection
from src.models.access_patterns import AccessPatternSignals
from src.models.migration_complexity import MigrationComplexitySignals
from src.models.availability_signals import AvailabilitySignals


class AssessmentPayload(BaseModel):
    """Complete data payload from all connectors, ready for scoring."""

    platform: str = Field(description="Source platform name")
    query_history: QueryHistory = Field(default_factory=lambda: QueryHistory(platform=""))
    table_metadata: TableMetadataCollection = Field(default_factory=lambda: TableMetadataCollection(platform=""))
    concurrency_signals: Optional[ConcurrencySignals] = None
    security_patterns: Optional[SecurityPatterns] = None
    cost_signals: Optional[CostSignals] = None
    access_patterns: Optional[AccessPatternSignals] = None
    migration_complexity: Optional[MigrationComplexitySignals] = None

    # Platform display name from connector
    platform_display_name: str = ""

    # Optional external context (item 7b: contract pressure, 7c: availability)
    contract_renewal_months: Optional[int] = Field(default=None, description="months until license renewal")
    has_pending_license_increase: bool = Field(default=False)
    availability_signals: Optional[AvailabilitySignals] = None
    workload_context: dict[str, Any] = Field(default_factory=dict, description="multi_region, dr_requirement, regulated")
    # SE-captured qualitative context from architecture interview (§12)
    interview_inputs: dict[str, Any] = Field(default_factory=dict, description="SE-captured context from architecture interview")

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
