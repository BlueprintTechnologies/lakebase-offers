"""CSV/JSON import fallback connector for on-premises or unsupported platforms."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals
from src.models.cost_signals import CostSignals
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class OnPremDumpConnector(AbstractBaseConnector):
    platform_name = "onprem_dump"
    platform_display_name = "On-Premises (Imported Dump)"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._csv_path = self._kwargs.get("onprem_csv_path")
        self._json_path = self._kwargs.get("onprem_json_path")
        self._delimiter = self._kwargs.get("onprem_delimiter", ",")

    def validate_credentials(self) -> bool:
        """Validate that at least one data source file exists."""
        if self._csv_path:
            if not Path(self._csv_path).exists():
                raise FileNotFoundError(f"On-prem CSV not found: {self._csv_path}")
        if self._json_path:
            if not Path(self._json_path).exists():
                raise FileNotFoundError(f"On-prem JSON not found: {self._json_path}")
        if not self._csv_path and not self._json_path:
            raise FileNotFoundError("On-prem: Provide either onprem_csv_path or onprem_json_path in config.")
        return True

    def fetch_query_history(self) -> QueryHistory:
        """Parse imported query history from CSV or JSON dump."""
        queries: list[QueryRecord] = []

        if self._csv_path:
            queries = self._parse_csv_queries(str(self._csv_path))
        elif self._json_path:
            queries = self._parse_json_queries(str(self._json_path))

        databases: set[str] = set()
        for q in queries:
            if q.database:
                databases.add(q.database)

        return QueryHistory(
            platform="onprem_dump",
            queries=queries,
            total_queries_fetched=len(queries),
            date_range_start=queries[0].first_executed if queries else None,
            date_range_end=queries[-1].last_executed if queries else None,
            unique_databases=list(databases),
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    def _parse_csv_queries(self, csv_path: str) -> list[QueryRecord]:
        queries: list[QueryRecord] = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qf = self._detect_pii_in_fingerprint(row.get("query_text", "") or row.get("sql", "") or "")
                queries.append(QueryRecord(
                    query_id=row.get("query_id", "") or f"onprem_{len(queries)}",
                    database=row.get("database", "") or row.get("db", "") or "",
                    schema_name=row.get("schema", "") or "",
                    query_text_fingerprint=self._hash_query_text(qf),
                    query_type=row.get("query_type", "OTHER").upper(),
                    avg_exec_time_ms=self._safe_float(row.get("avg_exec_time_ms")),
                    min_exec_time_ms=self._safe_float(row.get("min_exec_time_ms")),
                    max_exec_time_ms=self._safe_float(row.get("max_exec_time_ms")),
                    total_executions=self._safe_int(row.get("total_executions")),
                    avg_rows_returned=self._safe_float(row.get("avg_rows_returned")),
                    avg_bytes_scanned=self._safe_float(row.get("avg_bytes_scanned")),
                    last_executed=datetime.fromisoformat(row["last_executed"]) if row.get("last_executed") else None,
                    first_executed=datetime.fromisoformat(row["first_executed"]) if row.get("first_executed") else None,
                    has_udf=row.get("has_udf", "false").lower() == "true",
                    has_stored_procedure=row.get("has_stored_procedure", "false").lower() == "true",
                    timeout_count=self._safe_int(row.get("timeout_count")),
                    error_count=self._safe_int(row.get("error_count")),
                ))
        return queries

    def _parse_json_queries(self, json_path: str) -> list[QueryRecord]:
        with open(json_path) as f:
            data = json.load(f)

        raw_list = data if isinstance(data, list) else data.get("queries", [])
        queries: list[QueryRecord] = []
        for item in raw_list:
            qf = self._detect_pii_in_fingerprint(item.get("query_text", "") or item.get("sql", "") or "")
            queries.append(QueryRecord(
                query_id=item.get("query_id", "") or f"onprem_{len(queries)}",
                database=item.get("database", "") or "",
                schema_name=item.get("schema_name", "") or "",
                query_text_fingerprint=self._hash_query_text(qf),
                query_type=item.get("query_type", "OTHER").upper(),
                avg_exec_time_ms=self._safe_float(item.get("avg_exec_time_ms")),
                total_executions=self._safe_int(item.get("total_executions")),
                avg_rows_returned=self._safe_float(item.get("avg_rows_returned")),
                avg_bytes_scanned=self._safe_float(item.get("avg_bytes_scanned")),
                last_executed=datetime.fromisoformat(item["last_executed"]) if item.get("last_executed") else None,
                first_executed=datetime.fromisoformat(item["first_executed"]) if item.get("first_executed") else None,
                has_udf=item.get("has_udf", False),
                has_stored_procedure=item.get("has_stored_procedure", False),
                timeout_count=self._safe_int(item.get("timeout_count")),
                error_count=self._safe_int(item.get("error_count")),
            ))
        return queries

    def fetch_table_metadata(self) -> TableMetadataCollection:
        """Parse table metadata from imported CSV or JSON."""
        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        if self._csv_path:
            try:
                with open(self._csv_path, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        db = row.get("database", row.get("db", ""))
                        if db:
                            dbs.add(db)
                        sn = row.get("schema", row.get("schema_name", ""))
                        if sn:
                            schemas.add(sn)
                        tables.append(TableMetadata(
                            database=db,
                            schema_name=sn,
                            table_name=row.get("table_name", ""),
                            table_type=row.get("table_type", "TABLE").upper(),
                            row_count=self._safe_int(row.get("row_count")),
                            storage_size_bytes=self._safe_int(row.get("storage_size_bytes")),
                            is_sensitive="pii" in str(row.get("table_name", "")).lower(),
                        ))
            except Exception:
                tables = []
        elif self._json_path:
            with open(self._json_path) as f:
                data = json.load(f)
            raw_list = data if isinstance(data, list) else data.get("tables", [])
            for item in raw_list:
                db = item.get("database", "")
                sn = item.get("schema_name", "")
                if db:
                    dbs.add(db)
                if sn:
                    schemas.add(sn)
                tables.append(TableMetadata(
                    database=db,
                    schema_name=sn,
                    table_name=item.get("table_name", ""),
                    table_type=item.get("table_type", "TABLE").upper(),
                    row_count=self._safe_int(item.get("row_count")),
                    storage_size_bytes=self._safe_int(item.get("storage_size_bytes")),
                    is_sensitive="pii" in str(item.get("table_name", "")).lower(),
                ))

        total_bytes = sum(t.storage_size_bytes or 0 for t in tables)
        total_rows = sum(t.row_count or 0 for t in tables)

        return TableMetadataCollection(
            platform="onprem_dump",
            tables=tables,
            total_tables_fetched=len(tables),
            total_row_count=total_rows,
            total_storage_bytes=total_bytes,
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        return ConcurrencySignals(
            platform="onprem_dump",
            snapshots=[],
            avg_concurrent_queries=0.0,
            peak_concurrent_queries=0,
            scaling_pressure="unknown",
        )

    def fetch_cost_signals(self) -> CostSignals:
        """Estimate costs from table metadata in imported dump."""
        cost = CostSignals(platform="onprem_dump")
        total_storage_gb = 0.0
        if self._csv_path:
            total_storage_gb = self._get_csv_table_storage()
        elif self._json_path:
            total_storage_gb = self._get_json_table_storage()
        else:
            total_storage_gb = 50.0

        cost.compute_units_per_month = 0.0
        cost.compute_unit_name = "N/A (estimated)"
        cost.compute_cost_per_unit = 0.0
        cost.estimated_compute_cost_monthly = 300.0  # baseline
        cost.storage_gb_total = total_storage_gb
        cost.storage_cost_per_gb = 0.02
        cost.estimated_storage_cost_monthly = total_storage_gb * 0.02
        cost.bytes_scanned_per_month = 0.0
        cost.io_cost_per_mb = 0.000001
        cost.estimated_io_cost_monthly = 0.0
        cost.total_estimated_monthly_cost = 300.0 + total_storage_gb * 0.02
        cost.costs_from_billing_api = False
        return cost

    def _get_csv_table_storage(self) -> float:
        total = 0.0
        if self._csv_path:
            with open(self._csv_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    size = row.get("storage_size_bytes", row.get("bytes", "0"))
                    total += self._safe_int(size)
        return total / 1024 / 1024 / 1024 if total else 50.0

    def _get_json_table_storage(self) -> float:
        total = 0.0
        with open(self._json_path) as f:
            data = json.load(f)
        raw_list = data if isinstance(data, list) else data.get("tables", [])
        for item in raw_list:
            size = item.get("storage_size_bytes", item.get("bytes", 0))
            total += self._safe_int(size)
        return total / 1024 / 1024 / 1024 if total else 50.0

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="onprem_dump",
            findings=[
                SecurityFinding(
                    category="COMPLIANCE", severity="high",
                    description="On-premises platforms may lack enterprise compliance certifications. Review data handling procedures.",
                    remediation="Implement on-prem security controls matching BPCS baseline.",
                ),
            ],
            rbac_enabled=False,
            encryption_at_rest=False,
            encryption_in_transit=False,
            audit_logging_enabled=False,
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
        )
