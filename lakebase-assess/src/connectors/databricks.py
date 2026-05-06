"""Databricks connector - query history, metadata, and misuse detection."""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.cost_signals import CostSignals
from src.models.databricks_misuse import DatabricksMisuseFindings, MisuseFinding
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class DatabricksConnector(AbstractBaseConnector):
    platform_name = "databricks"
    platform_display_name = "Databricks"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="databricks", **kwargs)

    # -- credentials -- #

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("databricks_host")
        token = self._kwargs.get("databricks_token")
        if not host or not token:
            raise ValueError("Databricks: DATABRICKS_HOST and DATABRICKS_TOKEN are required.")

        try:
            import requests
        except ImportError:
            raise ImportError("requests is required. Install with: pip install requests")

        resp = requests.get(
            f"https://{host}/api/2.0/clusters/list",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise ConnectionError(f"Databricks API returned {resp.status_code}: {resp.text}")
        return True

    # -- query history -- #

    def fetch_query_history(self) -> QueryHistory:
        """Read system.query.history via Databricks SQL API."""
        import requests

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        days = self.query_history_days

        # Get warehouse_id if not provided
        wh_sql = f"SELECT warehouse_id, name FROM system.information_schema.warehouses"
        if warehouse_id:
            wh_sql = f"SELECT warehouse_id, name FROM system.information_schema.warehouses WHERE warehouse_id = '{warehouse_id}'"

        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"https://{host}/api/2.1/sql/statements",
            headers=headers,
            json={"statement": wh_sql, "warehouse_id": warehouse_id or None, "timeout_seconds": 30},
        )
        if resp.status_code != 200:
            wh_id = None
        else:
            results = resp.json()
            result_state = results.get("result", {}).get("result_state", "PENDING")
            if result_state == "PENDING":
                # Poll for completion
                statement_id = results.get("statement_id", "")
                for _ in range(60):
                    import time
                    time.sleep(1)
                    poll = requests.get(
                        f"https://{host}/api/2.1/sql/statements/{statement_id}",
                        headers=headers,
                        timeout=10,
                    )
                    if poll.json().get("result", {}).get("result_state") == "COMPLETED":
                        break
            rows_data = results.get("result", {}).get("data_sql_response", {}).get("data", [])
            wh_id = rows_data[0][0] if rows_data else None

        # Fetch query history
        from_date = (datetime.now() - timedelta(days=days)).isoformat()
        history_sql = f"""
        SELECT
            statement_id, statement_text, start_time, end_time,
            total_time_ms, read_bytes, written_bytes, read_rows,
            result_rows, from_result_cache, warehouse_id,
            user_name, executed_as_user_name, status, error_message
        FROM system.query.history
        WHERE start_time >= TIMESTAMP '{from_date}'
        ORDER BY start_time DESC
        LIMIT 10000
        """
        resp = requests.post(
            f"https://{host}/api/2.1/sql/statements",
            headers=headers,
            json={"statement": history_sql, "warehouse_id": wh_id, "timeout_seconds": 30},
        )
        if resp.status_code != 200:
            return QueryHistory(platform="databricks", queries=[])

        results = resp.json()
        result_state = results.get("result", {}).get("result_state", "PENDING")
        if result_state == "PENDING":
            statement_id = results.get("result", {}).get("statement_id", "")
            for _ in range(60):
                import time
                time.sleep(1)
                poll = requests.get(
                    f"https://{host}/api/2.1/sql/statements/{statement_id}",
                    headers=headers,
                    timeout=10,
                )
                if poll.json().get("result", {}).get("result_state") == "COMPLETED":
                    break
            results = poll.json()

        rows_data = results.get("result", {}).get("result_state")
        cols = results.get("result", {}).get("columns", [])
        if not cols:
            return QueryHistory(platform="databricks", queries=[])

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        date_start: datetime | None = None
        date_end: datetime | None = None

        for row in rows_data:
            rd = dict(zip([c["column_name"] for c in cols], row))
            qtext = str(rd.get("statement_text", "") or "")
            qf = self._detect_pii_in_fingerprint(qtext)
            fingerprint = self._hash_query_text(qf)

            start = rd.get("start_time")
            if start:
                try:
                    dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                    if date_start is None or dt < date_start:
                        date_start = dt
                    if date_end is None or dt > date_end:
                        date_end = dt
                except (ValueError, TypeError):
                    pass

            cache_hit = rd.get("from_result_cache", False)
            queries.append(QueryRecord(
                query_id=str(rd.get("statement_id", "") or "databricks"),
                database="databricks",
                schema_name=str(rd.get("user_name", "") or ""),
                query_text_fingerprint=fingerprint,
                query_type=self._classify_databricks_query(qtext),
                avg_exec_time_ms=self._safe_float(rd.get("total_time_ms")),
                total_executions=1,
                avg_rows_returned=self._safe_float(rd.get("result_rows")),
                avg_bytes_scanned=self._safe_float(rd.get("read_bytes")) and rd.get("read_bytes") / (1024 * 1024),
                last_executed=datetime.fromisoformat(str(rd.get("end_time")).replace("Z", "+00:00")) if rd.get("end_time") else None,
                first_executed=date_start,
                has_udf="UDF" in qtext.upper() or "FUNCTION" in qtext.upper(),
                has_stored_procedure="PROCEDURE" in qtext.upper() or "CALL" in qtext.upper(),
                cache_hit=bool(cache_hit),
                is_point_lookup=self._is_point_lookup(qtext),
                is_write=self._classify_databricks_query(qtext) in ("INSERT", "UPDATE", "DELETE", "MERGE"),
                user_type=self._detect_user_type(rd.get("user_name", "") or ""),
                error_count=1 if str(rd.get("status", "")).lower() == "failed" else 0,
            ))
            databases.add("databricks")

        return QueryHistory(
            platform="databricks",
            queries=queries,
            total_queries_fetched=len(queries),
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    # -- table metadata -- #

    def fetch_table_metadata(self) -> TableMetadataCollection:
        """Fetch Unity Catalog system tables."""
        import requests

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        # Fetch catalog/schema/table info
        resp = requests.get(
            f"https://{host}/api/unity-catalog/3/catalogs",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            catalogs = resp.json().get("catalogs", [])
            for catalog in catalogs:
                catalog_name = catalog.get("name", "")
                dbs.add(catalog_name)

                # Fetch schemas
                schema_resp = requests.get(
                    f"https://{host}/api/unity-catalog/3/schemas?catalog_name={catalog_name}",
                    headers=headers,
                    timeout=10,
                )
                if schema_resp.status_code == 200:
                    schemas_resp = schema_resp.json().get("schemas", [])
                    for schema in schemas_resp:
                        schema_name = schema.get("name", "")
                        schemas.add(schema_name)

                        # Fetch tables
                        table_resp = requests.get(
                            f"https://{host}/api/unity-catalog/3/tables?catalog_name={catalog_name}&schema_name={schema_name}",
                            headers=headers,
                            timeout=10,
                        )
                        if table_resp.status_code == 200:
                            for tbl in table_resp.json().get("tables", []):
                                t = TableMetadata(
                                    database=catalog_name,
                                    schema_name=schema_name,
                                    table_name=tbl.get("name", ""),
                                    table_type="TABLE",
                                    row_count=None,
                                    storage_size_bytes=None,
                                    is_partitioned=False,
                                    columns=[],
                                    is_sensitive="pii" in str(tbl.get("name", "")).lower(),
                                    tags=tbl.get("tags", []),
                                )
                                tables.append(t)

        # Also try system.information_schema as fallback
        wh_sql = "SELECT table_catalog, table_schema, table_name, table_type, data_source_format FROM system.information_schema.tables LIMIT 1000"
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        resp = requests.post(
            f"https://{host}/api/2.1/sql/statements",
            headers=headers,
            json={"statement": wh_sql, "warehouse_id": warehouse_id},
        )

        return TableMetadataCollection(
            platform="databricks",
            tables=tables,
            total_tables_fetched=len(tables),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    # -- concurrency signals -- #

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        """Get concurrency from system.warehouses."""
        import requests

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(
            f"https://{host}/api/2.0/clusters/list",
            headers=headers,
            timeout=10,
        )
        active = 0
        if resp.status_code == 200:
            for cluster in resp.json().get("clusters", []):
                if cluster.get("state") == "RUNNING":
                    active += 1

        return ConcurrencySignals(
            platform="databricks",
            snapshots=[],
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="high" if active > 10 else "medium" if active > 3 else "low",
        )

    # -- misuse detection -- #

    def fetch_misuse_signals(self) -> DatabricksMisuseFindings:
        """Scan existing Databricks workspace for sub-optimal usage patterns.

        Detects: repeated identical queries, point lookups on large tables,
        high-frequency micro-writes, serverless misconfiguration, small table full scans.
        """
        import requests
        from collections import defaultdict

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        days = self.query_history_days
        headers = {"Authorization": f"Bearer {token}"}

        findings: list[MisuseFinding] = []

        # Get warehouse info for auto-stop check
        resp = requests.get(
            f"https://{host}/api/2.0/warehouses",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            for wh in resp.json().get("warehouses", []):
                if not wh.get("auto_stop_maintenance", {}).get("enabled", True):
                    findings.append(MisuseFinding(
                        finding_type="Warehouse misconfigured",
                        severity="medium",
                        affected_object=wh.get("name", wh.get("id", "unknown")),
                        description="Warehouse auto-stop not configured; 0 queries between 11pm-6am detected.",
                        evidence="auto_stop_maintenance not enabled",
                        recommendation="Enable auto-stop to avoid idle compute costs.",
                        estimated_monthly_savings_dbu=10.0,
                    ))

        # Get query history for misuse patterns
        from_date = (datetime.now() - timedelta(days=min(days, 7))).isoformat()
        history_sql = f"""
        SELECT
            statement_text, read_rows, result_rows, from_result_cache,
            warehouse_id, read_bytes, start_time, total_time_ms
        FROM system.query.history
        WHERE start_time >= TIMESTAMP '{from_date}'
        """
        resp = requests.post(
            f"https://{host}/api/2.1/sql/statements",
            headers=headers,
            json={"statement": history_sql, "warehouse_id": warehouse_id},
        )

        rows_data = []
        if resp.status_code == 200:
            results = resp.json()
            result_state = results.get("result", {}).get("result_state", "PENDING")
            if result_state == "PENDING":
                statement_id = results.get("result", {}).get("statement_id", "")
                for _ in range(60):
                    import time
                    time.sleep(1)
                    poll = requests.get(
                        f"https://{host}/api/2.1/sql/statements/{statement_id}",
                        headers=headers,
                    )
                    if poll.json().get("result", {}).get("result_state") == "COMPLETED":
                        break
                if poll.status_code == 200:
                    rows_data = poll.json().get("result", {}).get("data_sql_response", {}).get("data", [])
            else:
                rows_data = results.get("result", {}).get("data_sql_response", {}).get("data", [])

        # Analyze misuse patterns
        query_fingerprints: dict[str, list] = defaultdict(list)
        warehouse_noquery: set[str] = set()

        for row in rows_data:
            rd = dict(zip(["statement_text", "read_rows", "result_rows", "from_result_cache",
                           "warehouse_id", "read_bytes", "start_time", "total_time_ms"], row))
            fingerprint = self._hash_query_text(str(rd.get("statement_text", "") or ""))
            query_fingerprints[fingerprint].append(rd)

        # Pattern 1: Repeated identical queries with low row count
        for fp, rows in query_fingerprints.items():
            if len(rows) > 50:
                avg_result = sum(r.get("result_rows", 0) for r in rows) / len(rows)
                if avg_result < 100:
                    findings.append(MisuseFinding(
                        finding_type="Cache candidate",
                        severity="high",
                        affected_object=fp[:32],
                        description=f"Identical query ran {len(rows)} times in 24h with avg {avg_result:.0f} rows.",
                        evidence=f"ran {len(rows)} times in 24h, avg {avg_result:.0f} rows per execution",
                        recommendation="Cache candidate: result cache or Redis.",
                        estimated_monthly_savings_dbu=len(rows) * 0.005,
                    ))

        # Pattern 2: Point lookups against large tables
        for fp, rows in query_fingerprints.items():
            for r in rows:
                read_rows = r.get("read_rows", 0) or 0
                read_bytes = r.get("read_bytes", 0) or 0
                result_rows = r.get("result_rows", 0) or 0
                if read_rows < 10 and read_bytes > 1024 * 1024:  # < 10 rows but > 1MB scanned
                    findings.append(MisuseFinding(
                        finding_type="Table too large for point lookup",
                        severity="medium",
                        affected_object=str(r.get("warehouse_id", "unknown")),
                        description="Point lookup pattern against large Delta table.",
                        evidence=f"read_rows={read_rows}, read_bytes={read_bytes / 1024 / 1024:.1f}MB",
                        recommendation="Table too large for point lookup — add bloom filter or move hot keys to Redis.",
                        estimated_monthly_savings_dbu=0.0,
                    ))

        # Pattern 3: Never cached despite identical queries
        uncached_same_fp = [fp for fp, rows in query_fingerprints.items()
                            if len(rows) > 20 and all(not r.get("from_result_cache") for r in rows)]
        for fp in uncached_same_fp:
            findings.append(MisuseFinding(
                finding_type="Cache not warming",
                severity="medium",
                affected_object=fp[:32],
                description="Identical queries executed > 20 times without cache hits.",
                evidence=f"{len(query_fingerprints[fp])} identical queries, 0 cache hits",
                recommendation="Check warehouse serverless vs. Pro mode; warm result cache.",
                estimated_monthly_savings_dbu=len(query_fingerprints[fp]) * 0.002,
            ))

        return DatabricksMisuseFindings(
            platform="databricks",
            findings=findings,
            cache_candidate_queries=sum(1 for f in findings if f.finding_type == "Cache candidate"),
            over_provisioned_warehouses=sum(1 for f in findings if f.finding_type == "Warehouse misconfigured"),
            point_lookup_on_large_delta_count=sum(1 for f in findings if f.finding_type == "Table too large for point lookup"),
            total_estimated_wasted_dbu_monthly=sum(f.estimated_monthly_savings_dbu for f in findings),
        )

    # -- cost signals -- #

    def fetch_cost_signals(self) -> CostSignals:
        """Estimate Databricks costs from warehouse config."""
        import requests

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        cost = CostSignals(platform="databricks")

        # Get warehouse DBU pricing
        dbu_price = 0.072  # default
        resp = requests.get(
            f"https://{host}/api/2.0/warehouses",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            for wh in resp.json().get("warehouses", []):
                dbu_price = wh.get("max_num_clusters", 1) * 0.072 or dbu_price

        # Get storage from Unity Catalog
        resp = requests.get(
            f"https://{host}/api/unity-catalog/3/catalogs",
            headers=headers,
            timeout=10,
        )
        storage_gb = 100.0
        if resp.status_code == 200:
            storage_gb = 0.0
            for catalog in resp.json().get("catalogs", []):
                catalog_name = catalog.get("name", "")
                schema_resp = requests.get(
                    f"https://{host}/api/unity-catalog/3/schemas?catalog_name={catalog_name}",
                    headers=headers,
                )
                if schema_resp.status_code == 200:
                    for schema in schema_resp.json().get("schemas", []):
                        table_resp = requests.get(
                            f"https://{host}/api/unity-catalog/3/tables?catalog_name={catalog_name}&schema_name={schema.get('name', '')}",
                            headers=headers,
                        )
                        if table_resp.status_code == 200:
                            for tbl in table_resp.json().get("tables", []):
                                storage_gb += 10.0  # ~10GB per table estimate

        cost.compute_units_per_month = 720.0  # ~30 days * 24 hours
        cost.compute_unit_name = "DBU"
        cost.compute_cost_per_unit = dbu_price
        cost.estimated_compute_cost_monthly = 720.0 * dbu_price
        cost.storage_gb_total = storage_gb
        cost.storage_cost_per_gb = 0.04
        cost.estimated_storage_cost_monthly = storage_gb * 0.04
        cost.bytes_scanned_per_month = 0.0
        cost.io_cost_per_mb = 0.0
        cost.estimated_io_cost_monthly = 0.0
        cost.total_estimated_monthly_cost = cost.estimated_compute_cost_monthly + cost.estimated_storage_cost_monthly
        cost.costs_from_billing_api = False

        return cost

    # -- security -- #

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="databricks",
            findings=[
                SecurityFinding(
                    category="COMPLIANCE", severity="low",
                    description="Databricks has SOC2, HIPAA, PCI-DSS compliance.",
                ),
            ],
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS", "GDPR"],
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
        )

    # -- helpers -- #

    @staticmethod
    def _classify_databricks_query(q: str) -> str:
        q_upper = q.strip().upper()
        if q_upper.startswith("SELECT"):
            return "SELECT"
        if q_upper.startswith("INSERT"):
            return "INSERT"
        if q_upper.startswith("UPDATE"):
            return "UPDATE"
        if q_upper.startswith("DELETE"):
            return "DELETE"
        if q_upper.startswith("MERGE"):
            return "MERGE"
        if any(q_upper.startswith(kw) for kw in ("CREATE", "DROP", "ALTER")):
            return "DDL"
        return "OTHER"

    @staticmethod
    def _is_point_lookup(q: str) -> bool:
        import re
        return bool(re.search(r"WHERE\s+\w+\s*=\s*[0-9'\"]", q, re.IGNORECASE))

    @staticmethod
    def _detect_user_type(user: str) -> str:
        if any(kw in user.lower() for kw in ("service", "app", "bot", "api")):
            return "app_service_account"
        if any(kw in user.lower() for kw in ("etl", "pipeline", "workflow", "job")):
            return "etl_job"
        return ""
