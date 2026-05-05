"""Teradata connector - read-only query history and metadata."""

import logging
from datetime import datetime
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class TeradataConnector(AbstractBaseConnector):
    platform_name = "teradata"
    platform_display_name = "Teradata"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="teradata", **kwargs)

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("teradata_host")
        user = self._kwargs.get("teradata_user")
        if not host or not user:
            raise ValueError("Teradata: TERADATA_HOST and TERADATA_USER are required.")

        try:
            import teradata
        except ImportError:
            raise ImportError("teradata Python package is required. Install with: pip install teradata")

        udl = f"odbc:driver={{Teradata}};dbq={self._kwargs.get('teradata_host', '')};hostname={host};port={int(self._kwargs.get('teradata_port', 1025))}"
        conn = teradata.UdaExec(appName="lakebase-assess", logError=False, logWarning=False, logInfo=False)
        session = None
        try:
            session = conn.createSession(udl, userName=user, password=self._kwargs.get("teradata_password", ""))
            session.execute("SELECT 1")
            return True
        except Exception as e:
            raise ConnectionError(f"Teradata connection failed: {e}")
        finally:
            if session:
                session.close()

    def fetch_query_history(self) -> QueryHistory:
        import teradata

        udl = f"odbc:driver={{Teradata}};dbq={self._kwargs.get('teradata_host', '')};hostname={self._kwargs.get('teradata_host', '')};port={int(self._kwargs.get('teradata_port', 1025))}"
        conn = teradata.UdaExec(appName="lakebase-assess", logError=False, logWarning=False, logInfo=False)
        session = conn.createSession(udl, userName=self._kwargs.get("teradata_user", ""), password=self._kwargs.get("teradata_password", ""))

        days = self.query_history_days
        sql = f"""
        SELECT
            requestid,
            requesttype,
            databasename,
            request,
            starttime,
            endtime,
            totalcpu,
            totaltime,
            logintime,
            rowcount,
            reqtext
        FROM dbc.dbqlogtbl
        WHERE logintime > CURRENT_DATE - INTERVAL '{days}' DAY
        ORDER BY logintime DESC
        LIMIT 10000
        """
        try:
            result = session.execute(sql)
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]
        finally:
            session.close()

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        date_start: datetime | None = None
        date_end: datetime | None = None

        for row in rows:
            rd = dict(zip(columns, row))
            qtext = str(rd.get("reqtext", "") or "")
            qf = self._detect_pii_in_fingerprint(qtext)
            fingerprint = self._hash_query_text(qf)

            st = rd.get("starttime")
            if st and isinstance(st, datetime):
                if date_start is None or st < date_start:
                    date_start = st
                if date_end is None or st > date_end:
                    date_end = st

            queries.append(QueryRecord(
                query_id=str(rd.get("requestid", "")),
                database=str(rd.get("databasename", "") or ""),
                schema_name="",
                query_text_fingerprint=fingerprint,
                query_type=str(rd.get("requesttype", "OTHER")).upper(),
                avg_exec_time_ms=self._safe_float(rd.get("totaltime")) and rd.get("totaltime") / 1000.0,
                total_executions=self._safe_int(rd.get("rowcount")),
                avg_rows_returned=self._safe_float(rd.get("rowcount")),
                last_executed=datetime.fromisoformat(str(rd.get("endtime"))) if rd.get("endtime") else None,
                first_executed=date_start,
                has_stored_procedure="SP" in str(rd.get("requesttype", "")).upper(),
            ))
            databases.add(rd.get("databasename"))

        return QueryHistory(
            platform="teradata",
            queries=queries,
            total_queries_fetched=len(rows),
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    def fetch_table_metadata(self) -> TableMetadataCollection:
        import teradata

        udl = f"odbc:driver={{Teradata}};dbq={self._kwargs.get('teradata_host', '')};hostname={self._kwargs.get('teradata_host', '')};port={int(self._kwargs.get('teradata_port', 1025))}"
        conn = teradata.UdaExec(appName="lakebase-assess", logError=False, logWarning=False, logInfo=False)
        session = conn.createSession(udl, userName=self._kwargs.get("teradata_user", ""), password=self._kwargs.get("teradata_password", ""))

        sql = """
        SELECT
            databasename,
            tablename,
            createtimestamp,
            columncount,
            perm Space / 1024 / 1024 as size_mb,
            avgsplit,
            maxblockid
        FROM dbc.tablesv
        WHERE tablekind = 'T'
        ORDER BY perm Space DESC
        """
        result = session.execute(sql)
        rows = result.fetchall()
        columns = [desc[0].lower() for desc in result.description]

        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        for row in rows:
            rd = dict(zip(columns, row))
            t = TableMetadata(
                database=str(rd.get("databasename", "") or ""),
                schema_name=str(rd.get("databasename", "") or ""),
                table_name=str(rd.get("tablename", "")),
                table_type="TABLE",
                storage_size_bytes=self._safe_int(rd.get("size_mb")) and rd.get("size_mb") * 1024 * 1024,
                column_count=self._safe_int(rd.get("columncount")),
            )
            tables.append(t)
            dbs.add(t.database)
            schemas.add(t.schema_name)

        session.close()
        return TableMetadataCollection(
            platform="teradata",
            tables=tables,
            total_tables_fetched=len(rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        import teradata

        udl = f"odbc:driver={{Teradata}};dbq={self._kwargs.get('teradata_host', '')};hostname={self._kwargs.get('teradata_host', '')};port={int(self._kwargs.get('teradata_port', 1025))}"
        conn = teradata.UdaExec(appName="lakebase-assess", logError=False, logWarning=False, logInfo=False)
        session = conn.createSession(udl, userName=self._kwargs.get("teradata_user", ""), password=self._kwargs.get("teradata_password", ""))

        session.execute("SELECT COUNT(*) FROM dbc.sessiont WHERE state = 'LOGGED IN'")
        active = session.fetchone()[0]
        session.close()

        return ConcurrencySignals(
            platform="teradata",
            snapshots=[],
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="high",
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        return SecurityPatterns(
            platform="teradata",
            findings=[
                SecurityFinding(
                    category="COMPLIANCE", severity="low",
                    description="Teradata has strong compliance certifications.",
                ),
            ],
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS"],
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
        )
