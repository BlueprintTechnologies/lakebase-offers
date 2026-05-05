"""Oracle connector - read-only query history and metadata."""

import logging
from datetime import datetime
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class OracleConnector(AbstractBaseConnector):
    platform_name = "oracle"
    platform_display_name = "Oracle Database"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="oracle", **kwargs)

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("oracle_host")
        user = self._kwargs.get("oracle_user")
        if not host or not user:
            raise ValueError("Oracle: ORACLE_HOST and ORACLE_USER are required.")

        try:
            import cx_Oracle
        except ImportError:
            raise ImportError("cx_Oracle or oracledb is required. Install with: pip install oracledb")

        conn_kwargs = {
            "user": user,
            "password": self._kwargs.get("oracle_password", ""),
            "dsn": f"{host}:{int(self._kwargs.get('oracle_port', 1521))}/{self._kwargs.get('oracle_service', '')}",
        }

        conn = None
        try:
            conn = cx_Oracle.connect(**conn_kwargs)
            conn.cursor().execute("SELECT 1 FROM DUAL")
            return True
        except (cx_Oracle.Error, cx_Oracle.OperationalError) as e:
            raise ConnectionError(f"Oracle connection failed: {e}")
        finally:
            if conn:
                conn.close()

    def fetch_query_history(self) -> QueryHistory:
        import cx_Oracle

        conn_kwargs = {
            "user": self._kwargs.get("oracle_user", ""),
            "password": self._kwargs.get("oracle_password", ""),
            "dsn": f"{self._kwargs.get('oracle_host', '')}:{int(self._kwargs.get('oracle_port', 1521))}/{self._kwargs.get('oracle_service', '')}",
        }
        conn = cx_Oracle.connect(**conn_kwargs)
        cur = conn.cursor()

        days = self.query_history_days
        sql = f"""
        SELECT
            sql_id,
            sql_fulltext,
            executions,
            elapsed_time / 1000000 as avg_exec_time_s,
            cpu_time / 1000000 as cpu_time_s,
            rows_processed,
            buffer_gets,
            disk_reads,
            first_load_time
        FROM v$sql
        WHERE first_load_time > SYSDATE - {days}
        ORDER BY elapsed_time DESC
        FETCH FIRST 10000 ROWS ONLY
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
            qtext = str(rd.get("sql_fulltext", "") or "")
            qf = self._detect_pii_in_fingerprint(qtext)
            fingerprint = self._hash_query_text(qf)

            flt = rd.get("first_load_time")
            if flt and isinstance(flt, datetime):
                if date_start is None or flt < date_start:
                    date_start = flt
                if date_end is None or flt > date_end:
                    date_end = flt

            queries.append(QueryRecord(
                query_id=str(rd.get("sql_id", "")),
                database=self._kwargs.get("oracle_service", ""),
                schema_name="",
                query_text_fingerprint=fingerprint,
                query_type=self._classify_oracle_query(qtext),
                avg_exec_time_ms=self._safe_float(rd.get("avg_exec_time_s")) and rd.get("avg_exec_time_s") * 1000.0,
                total_executions=self._safe_int(rd.get("executions")),
                avg_rows_returned=self._safe_float(rd.get("rows_processed")),
                avg_bytes_scanned=self._safe_float(rd.get("buffer_gets")) and rd.get("buffer_gets") * 8192.0,
                last_executed=flt,
                first_executed=date_start,
                has_udf="function" in qf.lower(),
                has_stored_procedure="procedure" in qf.lower() or "package" in qf.lower(),
            ))
            databases.add(self._kwargs.get("oracle_service", ""))

        cur.close()
        conn.close()
        return QueryHistory(
            platform="oracle",
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
    def _classify_oracle_query(q: str) -> str:
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
        import cx_Oracle

        conn_kwargs = {
            "user": self._kwargs.get("oracle_user", ""),
            "password": self._kwargs.get("oracle_password", ""),
            "dsn": f"{self._kwargs.get('oracle_host', '')}:{int(self._kwargs.get('oracle_port', 1521))}/{self._kwargs.get('oracle_service', '')}",
        }
        conn = cx_Oracle.connect(**conn_kwargs)
        cur = conn.cursor()

        sql = """
        SELECT
            owner,
            table_name,
            num_rows,
            bytes / 1024 / 1024 as size_mb,
            last_analyzed,
            partitioned,
            secondary
        FROM dba_tables
        WHERE num_rows > 0
        ORDER BY bytes DESC
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
                database=str(rd.get("owner", "") or ""),
                schema_name=str(rd.get("owner", "") or ""),
                table_name=str(rd.get("table_name", "")),
                table_type="TABLE",
                row_count=self._safe_int(rd.get("num_rows")),
                storage_size_bytes=self._safe_int(rd.get("size_mb")) and rd.get("size_mb") * 1024 * 1024,
                is_partitioned=str(rd.get("partitioned", "")).upper() == "YES",
                last_analyzed=rd.get("last_analyzed"),
                is_stale_stats=not bool(rd.get("last_analyzed")),
                is_sensitive="pii" in str(rd.get("table_name", "")).lower(),
            )
            tables.append(t)
            dbs.add(t.database)
            schemas.add(t.schema_name)

        cur.close()
        conn.close()
        return TableMetadataCollection(
            platform="oracle",
            tables=tables,
            total_tables_fetched=len(rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        import cx_Oracle

        conn_kwargs = {
            "user": self._kwargs.get("oracle_user", ""),
            "password": self._kwargs.get("oracle_password", ""),
            "dsn": f"{self._kwargs.get('oracle_host', '')}:{int(self._kwargs.get('oracle_port', 1521))}/{self._kwargs.get('oracle_service', '')}",
        }
        conn = cx_Oracle.connect(**conn_kwargs)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM v$session WHERE status = 'ACTIVE'")
        active = cur.fetchone()[0]
        conn.close()

        return ConcurrencySignals(
            platform="oracle",
            snapshots=[],
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="high" if active > 100 else "medium" if active > 20 else "low",
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="oracle",
            findings=[
                SecurityFinding(
                    category="COMPLIANCE", severity="low",
                    description="Oracle has strong compliance certifications (SOC2, HIPAA, PCI-DSS).",
                ),
                SecurityFinding(
                    category="RBAC", severity="medium",
                    description="Review Oracle fine-grained access control (FGAC) policies.",
                    remediation="Enable Oracle Label Security for column/row-level access.",
                ),
            ],
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS"],
            total_findings=2,
            high_severity_count=0,
            critical_severity_count=0,
        )
