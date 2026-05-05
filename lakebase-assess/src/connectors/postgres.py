"""PostgreSQL connector - read-only query history and metadata."""

import logging
from datetime import datetime
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class PostgresConnector(AbstractBaseConnector):
    platform_name = "postgres"
    platform_display_name = "PostgreSQL"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="postgres", **kwargs)

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("pg_host")
        user = self._kwargs.get("pg_user")
        if not host or not user:
            raise ValueError("PostgreSQL: PG_HOST and PG_USER are required.")

        try:
            import psycopg2
        except ImportError:
            raise ImportError("psycopg2-binary is required. Install with: pip install psycopg2-binary")

        conn_kwargs = {
            "dbname": self._kwargs.get("pg_database", "postgres"),
            "user": user,
            "host": host,
            "port": int(self._kwargs.get("pg_port", 5432)),
        }
        pw = self._kwargs.get("pg_password")
        if pw:
            conn_kwargs["password"] = pw

        conn = None
        try:
            conn = psycopg2.connect(**conn_kwargs)
            conn.cursor().execute("SELECT 1")
            return True
        except (psycopg2.Error, psycopg2.OperationalError) as e:
            raise ConnectionError(f"PostgreSQL connection failed: {e}")
        finally:
            if conn:
                conn.close()

    def fetch_query_history(self) -> QueryHistory:
        import psycopg2

        conn_kwargs = {
            "dbname": self._kwargs.get("pg_database", "postgres"),
            "user": self._kwargs.get("pg_user", ""),
            "host": self._kwargs.get("pg_host", ""),
            "port": int(self._kwargs.get("pg_port", 5432)),
        }
        pw = self._kwargs.get("pg_password")
        if pw:
            conn_kwargs["password"] = pw

        conn = psycopg2.connect(**conn_kwargs)
        cur = conn.cursor()

        days = self.query_history_days
        # Use pg_stat_statements if available, otherwise fall back to log_reader
        sql = f"""
        SELECT
            queryid,
            query,
            datname,
            usename,
            calls,
            total_exec_time,
            mean_exec_time,
            rows,
            shared_blks_hit,
            shared_blks_read,
            temp_blks_written,
            wal_bytes
        FROM pg_stat_statements
        WHERE total_exec_time > 0
        ORDER BY mean_exec_time DESC
        LIMIT 10000
        """
        cur.execute(sql)
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

            queries.append(QueryRecord(
                query_id=str(rd.get("queryid", "")) or f"pg_{hash(qf) % 10**9}",
                database=str(rd.get("datname", "") or ""),
                schema_name="",
                query_text_fingerprint=fingerprint,
                query_type=self._classify_postgres_query(qtext),
                avg_exec_time_ms=self._safe_float(rd.get("mean_exec_time")),
                total_executions=self._safe_int(rd.get("calls")),
                avg_rows_returned=self._safe_float(rd.get("rows")),
                avg_bytes_scanned=self._safe_float(rd.get("shared_blks_read")) and rd.get("shared_blks_read") * 8192.0,
                first_executed=date_start,
                has_udf="function" in qf.lower(),
                has_stored_procedure="call" in qf.lower() or "procedure" in qf.lower(),
            ))
            db = rd.get("datname")
            if db:
                databases.add(db)

        conn.close()
        return QueryHistory(
            platform="postgres",
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
    def _classify_postgres_query(q: str) -> str:
        q_upper = q.strip().upper()
        if q_upper.startswith("SELECT"):
            return "SELECT"
        if q_upper.startswith("INSERT"):
            return "INSERT"
        if q_upper.startswith("UPDATE"):
            return "UPDATE"
        if q_upper.startswith("DELETE"):
            return "DELETE"
        if any(q_upper.startswith(kw) for kw in ("CREATE", "DROP", "ALTER", "TRUNCATE")):
            return "DDL"
        return "OTHER"

    def fetch_table_metadata(self) -> TableMetadataCollection:
        import psycopg2

        conn_kwargs = {
            "dbname": self._kwargs.get("pg_database", "postgres"),
            "user": self._kwargs.get("pg_user", ""),
            "host": self._kwargs.get("pg_host", ""),
            "port": int(self._kwargs.get("pg_port", 5432)),
        }
        pw = self._kwargs.get("pg_password")
        if pw:
            conn_kwargs["password"] = pw

        conn = psycopg2.connect(**conn_kwargs)
        cur = conn.cursor()

        sql = """
        SELECT
            schemaname,
            tablename,
            tableowner,
            pg_table_size(schemaname || '.' || tablename) as table_size_bytes,
            n_live_tup as row_count,
            last_analyze,
            is_partition_table
        FROM pg_stat_user_tables
        ORDER BY pg_table_size(schemaname || '.' || tablename) DESC
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
                database=self._kwargs.get("pg_database", "postgres"),
                schema_name=str(rd.get("schemaname", "") or "public"),
                table_name=str(rd.get("tablename", "")),
                table_type="TABLE",
                row_count=self._safe_int(rd.get("row_count")),
                storage_size_bytes=self._safe_int(rd.get("table_size_bytes")),
                last_analyzed=rd.get("last_analyze"),
                is_stale_stats=not bool(rd.get("last_analyze")),
                is_sensitive="pii" in str(rd.get("tablename", "")).lower(),
            )
            tables.append(t)
            dbs.add(t.database)
            schemas.add(t.schema_name)

        conn.close()
        return TableMetadataCollection(
            platform="postgres",
            tables=tables,
            total_tables_fetched=len(rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        import psycopg2

        conn_kwargs = {
            "dbname": self._kwargs.get("pg_database", "postgres"),
            "user": self._kwargs.get("pg_user", ""),
            "host": self._kwargs.get("pg_host", ""),
            "port": int(self._kwargs.get("pg_port", 5432)),
        }
        pw = self._kwargs.get("pg_password")
        if pw:
            conn_kwargs["password"] = pw

        conn = psycopg2.connect(**conn_kwargs)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        active = cur.fetchone()[0]
        conn.close()

        return ConcurrencySignals(
            platform="postgres",
            snapshots=[],
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="medium" if active > 10 else "low",
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="postgres",
            findings=[
                SecurityFinding(
                    category="RBAC", severity="medium",
                    description="PostgreSQL RBAC is basic. Review pg_roles for least-privilege.",
                    remediation="Audit pg_roles and revoke PUBLIC access from sensitive objects.",
                ),
            ],
            rbac_enabled=True,
            encryption_at_rest=False,
            encryption_in_transit=True,
            audit_logging_enabled=False,
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
        )
