"""Abstract base connector for all platform implementations."""

import abc
import hashlib
import logging
from typing import Any

from src.models.assessment_payload import AssessmentPayload
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import TableMetadataCollection
from src.models.concurrency import ConcurrencySignals
from src.models.security import SecurityPatterns

logger = logging.getLogger(__name__)


class AbstractBaseConnector(abc.ABC):
    """Base class for platform-specific data ingestion connectors."""

    # Override in subclass
    platform_name: str = "base"
    platform_display_name: str = "Base"

    def __init__(
        self,
        platform_name: str = "base",
        query_history_days: int = 90,
        **kwargs: Any,
    ) -> None:
        self.platform_name = platform_name
        self.query_history_days = query_history_days
        self._kwargs = kwargs
        self._connected = False

    @abc.abstractmethod
    def validate_credentials(self) -> bool:
        """Validate that credentials are correct. Raises on failure."""
        ...

    @abc.abstractmethod
    def fetch_query_history(self) -> QueryHistory:
        """Fetch query history for the configured time window."""
        ...

    @abc.abstractmethod
    def fetch_table_metadata(self) -> TableMetadataCollection:
        """Fetch table metadata across all accessible databases."""
        ...

    @abc.abstractmethod
    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        """Fetch concurrency and performance signals."""
        ...

    @abc.abstractmethod
    def fetch_security_patterns(self) -> SecurityPatterns:
        """Fetch security and compliance patterns."""
        ...

    def ingest_all(self) -> AssessmentPayload:
        """Run full ingestion pipeline and return a validated AssessmentPayload."""
        # Validate first
        self.validate_credentials()

        qh = self.fetch_query_history()
        tm = self.fetch_table_metadata()
        cs = self.fetch_concurrency_signals()
        sp = self.fetch_security_patterns()

        payload = AssessmentPayload(
            platform=self.platform_name,
            platform_display_name=self.platform_display_name,
            query_history=qh,
            table_metadata=tm,
            concurrency_signals=cs,
            security_patterns=sp,
        )

        # Validate the full payload
        AssessmentPayload.model_validate(payload.model_dump())
        return payload

    # -- helpers -- #

    @staticmethod
    def _hash_query_text(text: str, length: int = 64) -> str:
        """Create a non-reversible fingerprint of query text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]

    @staticmethod
    def _detect_pii_in_fingerprint(text: str) -> str:
        """Mask known PII patterns in query text."""
        import re

        masks = [
            (r"\d{3}-\d{2}-\d{4}", "[SSN]"),
            (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", "[EMAIL]"),
            (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]"),
            (r"(?i)(password\s*=\s*)\S+", r"\1[REDACTED]"),
            (r"(?i)(api[_-]?key\s*=\s*)\S+", r"\1[REDACTED]"),
            (r"(?i)(secret\s*=\s*)\S+", r"\1[REDACTED]"),
        ]
        for pattern, replacement in masks:
            text = re.sub(pattern, replacement, text)
        return text

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        try:
            return int(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(val: Any, default: float | None = None) -> float | None:
        try:
            if val is None:
                return default
            return float(val)
        except (TypeError, ValueError):
            return default

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform_name}>"
