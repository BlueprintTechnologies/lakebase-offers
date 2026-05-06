"""Pydantic models for the assessment pipeline."""

from src.models.access_patterns import AccessPatternSignals, CacheCandidate, QueryTemporalBucket
from src.models.availability_signals import AvailabilitySignals
from src.models.cost_signals import CostSignals
from src.models.databricks_misuse import DatabricksMisuseFindings, MisuseFinding
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import ColumnSpec, TableMetadata, TableMetadataCollection
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.migration_complexity import (
    MigrationComplexitySignals,
    UDFRecord,
    StoredProcRecord,
    BinaryColumnRecord,
)

__all__ = [
    # Query history
    "QueryRecord",
    "QueryHistory",
    # Table metadata
    "TableMetadata",
    "TableMetadataCollection",
    "ColumnSpec",
    # Concurrency
    "ConcurrencySignals",
    "ConcurrencySnapshot",
    # Security
    "SecurityFinding",
    "SecurityPatterns",
    # Cost
    "CostSignals",
    # Access patterns
    "AccessPatternSignals",
    "CacheCandidate",
    "QueryTemporalBucket",
    # Migration complexity
    "MigrationComplexitySignals",
    "UDFRecord",
    "StoredProcRecord",
    "BinaryColumnRecord",
    # Databricks misuse
    "DatabricksMisuseFindings",
    "MisuseFinding",
    # Availability
    "AvailabilitySignals",
]
