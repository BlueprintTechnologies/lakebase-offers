"""Vertica connector - read-only query history and metadata."""

import logging
from datetime import datetime
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class VerticaConnector(AbstractBaseConnector):
    platform_name = "vertica"
    platform_display_name = "Vertica"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="vertica", **kwargs)

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("vertica_host")
        user = self._kwargs.get("vertica_user")
        if not host or not user:
            raise ValueError("Vertica: VERTICA_HOST and VERTICA_USER are required.")

        try:
            import vertica_python
        except ImportError:
            raise ImportError("vertica-python is required. Install with: pip install vertica-python")

        conn_kwargs = {
            "host": host,
            "port": int(self._kwargs.get("vertica_port", 5433)),
            "username": user,
            "password": self._kwargs.get("vertica_password", ""),
            "database": self._kwargs.get("vertica_database", "demo"),
        }

        conn = None
        try:
            conn = vertica_python.connect(**conn_kwargs)
            conn.cursor().execute("SELECT 1")
            return True
        except (vertica_python.errors.Error, vertica_python.errors.OperationalError) as e:
            raise ConnectionError(f"Vertica connection failed: {e}")
        finally:
            if conn:
                conn.close()

    def fetch_query_history(self) -> QueryHistory:
        import vertica_python

        conn_kwargs = {
            "host": self._kwargs.get("vertica_host", ""),
            "port": int(self._kwargs.get("vertica_port", 5433)),
            "username": self._kwargs.get("vertica_user", ""),
            "password": self._kwargs.get("vertica_password", ""),
            "database": self._kwargs.get("vertica_database", "demo"),
        }
        conn = vertica_python.connect(**conn_kwargs)
        cur = conn.cursor()

        days = self.query_history_days
        sql = f"""
        SELECT
            query_id,
            query,
            session_user,
            start_time,
            end_time,
            duration / 1000.0 as duration_ms,
            returned_rows,
            scanned_rows,
            scanned_bytes,
            rejected_rows,
            is_system
        FROM v_monitor.query_executor
        WHERE start_time > NOW() - INTERVAL '{days} days'
        ORDER BY start_time DESC
        LIMIT 10000
        """
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        except Exception:
            # Fallback: query from query_log table
            cur.execute("""
                SELECT
                    query_id, query, session_user, start_time, end_time,
                    duration_ms, returned_rows, scanned_rows, scanned_bytes
                FROM query_log
                WHERE start_time > NOW() - INTERVAL '%s days'
                ORDER BY start_time DESC LIMIT 10000
            """ % days)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        date_start: datetime | None = None
        date_end: datetime | None = None

        for row in rows:
            rd = dict(zip(columns, row))
            qtext = str(rd.get("query", "") or "")
            qf = self._detect_pii_in_fingerprint(qtext)
            fingerprint = self._hash_query_text(qf)

            st = rd.get("start_time")
            if st and isinstance(st, datetime):
                if date_start is None or st < date_start:
                    date_start = st
                if date_end is None or st > date_end:
                    date_end = st

            queries.append(QueryRecord(
                query_id=str(rd.get("query_id", "")),
                database=self._kwargs.get("vertica_database", "demo"),
                schema_name="",
                query_text_fingerprint=fingerprint,
                query_type=self._classify_query(qtext),
                avg_exec_time_ms=self._safe_float(rd.get("duration_ms")),
                total_executions=self._safe_int(rd.get("returned_rows")),
                avg_rows_returned=self._safe_float(rd.get("scanned_rows")),
                avg_bytes_scanned=self._safe_float(rd.get("scanned_bytes")),
                last_executed=datetime.fromisoformat(str(rd.get("end_time"))) if rd.get("end_time") else None,
                first_executed=date_start,
                has_udf="udf" in qf.lower(),
                has_stored_procedure="procedure" in qf.lower(),
            ))
            databases.add(self._kwargs.get("vertica_database", "demo"))

        cur.close()
        conn.close()
        return QueryHistory(
            platform="vertica",
            queries=queries,
            total_queries_fetched=len(rows),
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    @staticmethod
    def _classify_query(q: str) -> str:
        q_upper = q.strip().upper()
        if q_upper.startswith("SELECT"):
            return "SELECT"
        if q_upper.startswith("INSERT"):
            return "INSERT"
        if q_upper.startswith("UPDATE"):
            return "UPDATE"
        if q_upper.startswith("DELETE"):
            return "DELETE"
        if any(q_upper.startswith(kw) for kw in ("CREATE", "DROP", "ALTER")):
            return "DDL"
        return "OTHER"

    def fetch_table_metadata(self) -> TableMetadataCollection:
        import vertica_python

        conn_kwargs = {
            "host": self._kwargs.get("vertica_host", ""),
            "port": int(self._kwargs.get("vertica_port", 5433)),
            "username": self._kwargs.get("vertica_user", ""),
            "password": self._kwargs.get("vertica_password", ""),
            "database": self._kwargs.get("vertica_database", "demo"),
        }
        conn = vertica_python.connect(**conn_kwargs)
        cur = conn.cursor()

        sql = """
        SELECT
            table_schema,
            table_name,
            total_rows,
            total_bytes,
            is_segment_offload,
            is_dist_key,
            is_sort_key
        FROM v_catalog.tables
        WHERE table_type = 'BASE TABLE'
        ORDER BY total_bytes DESC
        """
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]

        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        for row in rows:
            rd = dict(zip(columns, row))
            t = TableMetadata(
                database=self._kwargs.get("vertica_database", "demo"),
                schema_name=str(rd.get("table_schema", "") or ""),
                table_name=str(rd.get("table_name", "")),
                table_type="TABLE",
                row_count=self._safe_int(rd.get("total_rows")),
                storage_size_bytes=self._safe_int(rd.get("total_bytes")),
                is_partitioned=str(rd.get("is_segment_offload", "")).upper() == "Y",
                is_clustering_key=str(rd.get("is_dist_key", "")).upper() == "Y",
                clustering_columns=["DISTKEY"] if str(rd.get("is_dist_key", "")).upper() == "Y" else [],
                is_sensitive="pii" in str(rd.get("table_name", "")).lower(),
            )
            tables.append(t)
            dbs.add(t.database)
            schemas.add(t.schema_name)

        cur.close()
        conn.close()
        return TableMetadataCollection(
            platform="vertica",
            tables=tables,
            total_tables_fetched=len(rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        import vertica_python

        conn_kwargs = {
            "host": self._kwargs.get("vertica_host", ""),
            "port": int(self._kwargs.get("vertica_port", 5433)),
            "username": self._kwargs.get("vertica_user", ""),
            "password": self._kwargs.get("vertica_password", ""),
            "database": self._kwargs.get("vertica_database", "demo"),
        }
        conn = vertica_python.connect(**conn_kwargs)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM v_monitor.session_info WHERE session_state = 'active'")
        active = cur.fetchone()[0]
        conn.close()

        return ConcurrencySignals(
            platform="vertica",
            snapshots=[],
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="high" if active > 50 else "medium" if active > 10 else "low",
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="vertica",
            findings=[
                SecurityFinding(
                    category="RBAC", severity="medium",
                    description="Review Vertica access controls for least-privilege.",
                ),
            ],
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=False,
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
        )
