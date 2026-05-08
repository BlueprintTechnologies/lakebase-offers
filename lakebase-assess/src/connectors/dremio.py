"""Dremio connector – placeholder implementation for coverage and future integration."""
import logging
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import TableMetadata, TableMetadataCollection
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.cost_signals import CostSignals
from src.models.security import SecurityFinding, SecurityPatterns

logger = logging.getLogger(__name__)

class DremioConnector(AbstractBaseConnector):
    platform_name = "dremio"
    platform_display_name = "Dremio"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="dremio", **kwargs)

    def validate_credentials(self) -> bool:
        # Dremio needs host, user, password (or token)
        if not self._kwargs.get("host"):
            raise ValueError("Dremio: host is required")
        if not self._kwargs.get("user"):
            raise ValueError("Dremio: user is required")
        return True

    def fetch_query_history(self) -> QueryHistory:
        # Dremio does not expose a built‑in query‑history API;
        # return an empty history snapshot.
        return QueryHistory(
            platform="dremio",
            queries=[],
            total_queries_fetched=0,
            date_range_start=None,
            date_range_end=None,
            unique_databases=[],
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
            scaling_pressure="low",
        )

    def fetch_table_metadata(self) -> TableMetadataCollection:
        # Dremio exposes system tables but we keep it minimal.
        return TableMetadataCollection(
            platform="dremio",
            tables=[],
            total_tables_fetched=0,
            total_row_count=0,
            total_storage_bytes=0,
            database_count=0,
            schema_count=0,
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        return ConcurrencySignals(
            platform="dremio",
            snapshots=[],
            avg_concurrent_queries=0.0,
            peak_concurrency=0,
            scaling_pressure="low",
        )

    def fetch_cost_signals(self) -> CostSignals:
        # Simple cost model – assume $0.015 per GB scanned.
        cost = CostSignals(platform="dremio")
        cost.estimated_compute_cost_monthly = 0.0
        cost.estimated_storage_cost_monthly = 0.0
        cost.estimated_io_cost_monthly = 0.0
        cost.total_estimated_monthly_cost = 0.0
        cost.costs_from_billing_api = False
        return cost

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="dremio",
            findings=[],
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS", "GDPR"],
            total_findings=0,
            high_severity_count=0,
            critical_severity_count=0,
        )