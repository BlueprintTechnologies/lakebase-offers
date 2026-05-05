"""Snowflake connector - read-only query history and metadata."""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import ColumnSpec, TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class SnowflakeConnector(AbstractBaseConnector):
    platform_name = "snowflake"
    platform_display_name = "Snowflake"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="snowflake", **kwargs)

    def validate_credentials(self) -> bool:
        account = self._kwargs.get("snowflake_account")
        user = self._kwargs.get("snowflake_user")
        if not account or not user:
            raise ValueError("Snowflake: SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER are required.")
        try:
            import snowflake.connector
        except ImportError:
            raise ImportError("snowflake-connector-python is required. Install with: pip install snowflake-connector-python")

        conn_kwargs = {
            "account": account,
            "user": user,
            "warehouse": self._kwargs.get("snowflake_warehouse", "COMPUTE_WH"),
            "role": self._kwargs.get("snowflake_role"),
            "database": self._kwargs.get("snowflake_database"),
            "schema": self._kwargs.get("snowflake_schema"),
        }
        if self._kwargs.get("snowflake_password"):
            conn_kwargs["password"] = self._kwargs["snowflake_password"]
        else:
            # Try key-based auth
            raise ValueError("Snowflake: SNOWFLAKE_PASSWORD or key-based auth must be configured.")

        conn = None
        try:
            conn = snowflake.connector.connect(**conn_kwargs)
            conn.cursor().execute("SELECT CURRENT_USER()")
            return True
        except snowflake.connector.errors.Error as e:
            raise ConnectionError(f"Snowflake connection failed: {e}")
        finally:
            if conn:
                conn.close()

    def fetch_query_history(self) -> QueryHistory:
        """Query Snowflake QUERY_HISTORY table function."""
        if not self._connected:
            self.validate_credentials()

        conn = self._snowflake_connect()
        cur = conn.cursor()

        days = self.query_history_days
        date_filter = f"RESULT_SERVICE_PERIOD > DATEADD(day, -{days}, CURRENT_TIMESTAMP())"

        sql = f"""
        SELECT
            QUERY_ID,
            QUERY_TEXT,
            DATABASE_NAME,
            SCHEMA_NAME,
            QUERY_TYPE,
            TOTAL_ELAPSED_TIME,
            ROWS_PRODUCED,
            BYTES_SCANNED,
            CONCURRENT_CONCURRENCY,
            QUERY_FAILURES,
            QUERY_STATUS,
            START_TIME,
            END_TIME,
            IS_CLIENT_QUERY_AGENT_REPORTING,
            HAS_OUT_PUT_PARAMS,
            SESSION_ID
        FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
            RESULT_LIMIT => 10000,
            {date_filter}
        ))
        ORDER BY START_TIME DESC
        """

        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        tables_set: set[str] = set()
        total_concurrency = 0
        peak_concurrency = 0
        date_start: datetime | None = None
        date_end: datetime | None = None

        for row in rows:
            row_dict = dict(zip(columns, row))
            qf = self._detect_pii_in_fingerprint(str(row_dict.get("QUERY_TEXT", "")))
            fingerprint = self._hash_query_text(qf)

            start = row_dict.get("START_TIME")
            if start:
                try:
                    dt = datetime.fromisoformat(str(start)) if isinstance(start, str) else start
                    if date_start is None or dt < date_start:
                        date_start = dt
                    if date_end is None or dt > date_end:
                        date_end = dt
                except (ValueError, TypeError):
                    pass

            queries.append(QueryRecord(
                query_id=str(row_dict.get("QUERY_ID", "")),
                database=str(row_dict.get("DATABASE_NAME", "") or ""),
                schema_name=str(row_dict.get("SCHEMA_NAME", "") or ""),
                query_text_fingerprint=fingerprint,
                query_type=str(row_dict.get("QUERY_TYPE", "OTHER")).upper(),
                avg_exec_time_ms=self._safe_float(row_dict.get("TOTAL_ELAPSED_TIME")) and self._safe_float(row_dict.get("TOTAL_ELAPSED_TIME")) / 1000.0,
                total_executions=self._safe_int(row_dict.get("ROWS_PRODUCED", 1)),
                avg_rows_returned=self._safe_float(row_dict.get("ROWS_PRODUCED")),
                avg_bytes_scanned=self._safe_float(row_dict.get("BYTES_SCANNED")),
                last_executed=datetime.fromisoformat(str(row_dict.get("END_TIME"))) if row_dict.get("END_TIME") else None,
                first_executed=date_start,
                has_udf="UDF" in str(row_dict.get("QUERY_TEXT", "")).upper(),
                has_stored_procedure="PROCEDURE" in str(row_dict.get("QUERY_TEXT", "")).upper() or "CALL" in str(row_dict.get("QUERY_TYPE", "")).upper(),
                timeout_count=self._safe_int(row_dict.get("QUERY_FAILURES", 0)),
                error_count=1 if str(row_dict.get("QUERY_STATUS", "")).lower() == "error" else 0,
            ))

            db = row_dict.get("DATABASE_NAME")
            if db:
                databases.add(db)

        conn.close()

        return QueryHistory(
            platform="snowflake",
            queries=queries,
            total_queries_fetched=len(rows),
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=list(tables_set),
            avg_concurrency=float(total_concurrency / max(len(queries), 1)),
            peak_concurrency=peak_concurrency or 10,
        )

    def fetch_table_metadata(self) -> TableMetadataCollection:
        conn = self._snowflake_connect()
        cur = conn.cursor()

        sql = """
        SELECT
            TABLE_CATALOG AS database_name,
            TABLE_SCHEMA AS schema_name,
            TABLE_NAME,
            TABLE_TYPE,
            ROW_COUNT,
            BYTES,
            LAST_ALTERED,
            IS_MATERIALIZED
        FROM INFORMATION_SCHEMA.TABLES
        ORDER BY BYTES DESC
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
                database=str(rd.get("database_name", "") or ""),
                schema_name=str(rd.get("schema_name", "") or ""),
                table_name=str(rd.get("table_name", "")),
                table_type=str(rd.get("table_type", "TABLE")).upper(),
                row_count=self._safe_int(rd.get("row_count")),
                storage_size_bytes=self._safe_int(rd.get("bytes")),
                is_partitioned=False,
                column_count=self._safe_int(rd.get("column_count", 0)),
                last_analyzed=datetime.fromisoformat(str(rd.get("last_altered"))) if rd.get("last_altered") else None,
                is_stale_stats=False,
                is_sensitive="PII" in str(rd.get("tags", "")).upper() or "SENSITIVE" in str(rd.get("tags", "")).upper(),
            )
            tables.append(t)
            dbs.add(t.database)
            schemas.add(t.schema_name)

        conn.close()
        return TableMetadataCollection(
            platform="snowflake",
            tables=tables,
            total_tables_fetched=len(rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        conn = self._snowflake_connect()
        cur = conn.cursor()

        sql = """
        SELECT
            START_TIME,
            ACTIVE_TIME,
            QUEUED_TIME,
            BLOCKING_ACTIVE_TIME,
            PROVISIONED_CONNECTIONS,
            TOTAL_SESSIONS,
            ACTIVE_SESS,
            PENDING_SESS,
            BLOCKED_SESS,
            CPU,
            MEMORY
        FROM TABLE(INFORMATION_SCHEMA.QUERY_ACROSS_HISTORY(
            EVENT_NAME => 'query_across_history',
            RESULT_LIMIT => 5000,
            EVENT_TIMESTAMP_START => DATEADD(day, -30, CURRENT_TIMESTAMP())
        ))
        """
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]

        snapshots: list[ConcurrencySnapshot] = []
        conns = []
        for row in rows:
            rd = dict(zip(columns, row))
            ts = str(rd.get("start_time", ""))
            active = self._safe_int(rd.get("active_sess"))
            conns.append(active)
            snapshots.append(ConcurrencySnapshot(
                timestamp=ts,
                active_sessions=active,
                queued_queries=self._safe_int(rd.get("pending_sess")),
                avg_wait_time_ms=self._safe_float(rd.get("queued_time")) and rd.get("queued_time") / 1000.0,
                resource_utilization_cpu=self._safe_float(rd.get("cpu")),
                resource_utilization_memory=self._safe_float(rd.get("memory")),
            ))

        conn.close()
        avg_c = float(sum(conns) / max(len(conns), 1))
        peak_c = max(conns) if conns else 0

        if peak_c > 100 or avg_c > 50:
            pressure = "critical"
        elif peak_c > 50 or avg_c > 25:
            pressure = "high"
        elif peak_c > 20 or avg_c > 10:
            pressure = "medium"
        else:
            pressure = "low"

        return ConcurrencySignals(
            platform="snowflake",
            snapshots=snapshots[:500],
            avg_concurrent_queries=avg_c,
            peak_concurrent_queries=peak_c,
            scaling_pressure=pressure,
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        conn = self._snowflake_connect()
        cur = conn.cursor()
        findings: list[SecurityFinding] = []

        # Check RBAC
        cur.execute("SHOW ROLES")
        rbac_rows = cur.fetchall()
        rbac_depth = 0
        for row in rbac_rows:
            rbac_depth = max(rbac_depth, len(str(row)) )

        rbac_enabled = len(rbac_rows) > 0

        # Check encryption
        cur.execute("SHOW PARAMETERS LIKE 'ENABLE_DECRYPTION'")
        enc_rows = cur.fetchall()
        encryption_at_rest = bool(enc_rows)

        # Check audit
        cur.execute("SHOW PARAMETERS LIKE 'QUERY_INTEGRITY'")
        audit_rows = cur.fetchall()
        audit_enabled = bool(audit_rows)

        # Check row-level security (Dynamic Data Masking)
        cur.execute("SHOW MASKING POLICIES")
        mdp_rows = cur.fetchall()
        rls = len(mdp_rows) > 0

        # Check SSO / SCIM
        cur.execute("SHOW EXTERNAL OAuth PROVIDERS")
        oauth_rows = cur.fetchall()
        sso = len(oauth_rows) > 0

        if not rbac_enabled:
            findings.append(SecurityFinding(
                category="RBAC", severity="high",
                description="No RBAC roles detected. All users may have unrestricted access.",
                remediation="Implement role-based access control with least-privilege principle.",
            ))
        if not encryption_at_rest:
            findings.append(SecurityFinding(
                category="ENCRYPTION", severity="medium",
                description="Encryption at rest may not be enabled.",
                remediation="Enable TDE or column-level encryption for sensitive data.",
            ))
        if not audit_enabled:
            findings.append(SecurityFinding(
                category="AUDIT", severity="high",
                description="Audit logging may not be fully enabled.",
                remediation="Enable ACCOUNT_ACCESS and QUERY_LOGGING policies.",
            ))
        if not sso:
            findings.append(SecurityFinding(
                category="ACCESS_CONTROL", severity="medium",
                description="No external SSO provider configured.",
                remediation="Configure SCIM provisioning with an identity provider.",
            ))

        conn.close()

        return SecurityPatterns(
            platform="snowflake",
            findings=findings,
            rbac_enabled=rbac_enabled,
            rbac_depth=rbac_depth,
            encryption_at_rest=encryption_at_rest,
            encryption_in_transit=True,  # Snowflake defaults to TLS
            audit_logging_enabled=audit_enabled,
            row_level_security=rls,
            sso_integration=sso,
            mfa_required=True,  # Snowflake enforces MFA by default
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS", "GDPR"],
            total_findings=len(findings),
            high_severity_count=sum(1 for f in findings if f.severity == "high"),
            critical_severity_count=sum(1 for f in findings if f.severity == "critical"),
        )

    def _snowflake_connect(self):
        import snowflake.connector
        conn_kwargs = {
            "account": self._kwargs.get("snowflake_account", ""),
            "user": self._kwargs.get("snowflake_user", ""),
            "warehouse": self._kwargs.get("snowflake_warehouse", "COMPUTE_WH"),
            "role": self._kwargs.get("snowflake_role"),
            "database": self._kwargs.get("snowflake_database"),
            "schema": self._kwargs.get("snowflake_schema"),
        }
        pw = self._kwargs.get("snowflake_password")
        if pw:
            conn_kwargs["password"] = pw
        conn = snowflake.connector.connect(**conn_kwargs)
        self._connected = True
        return conn
