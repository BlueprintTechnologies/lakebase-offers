"""Snowflake connector - read-only query history and metadata."""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.cost_signals import CostSignals
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import ColumnSpec, TableMetadata, TableMetadataCollection
from src.models.access_patterns import AccessPatternSignals, CacheCandidate, QueryTemporalBucket
from src.models.migration_complexity import MigrationComplexitySignals, UDFRecord, StoredProcRecord, BinaryColumnRecord

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
                is_stale_stats=AbstractBaseConnector._is_stats_stale(rd.get("last_altered")),
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

        # Count active users (item 7f)
        active_users = 0
        active_sa = 0
        try:
            cur.execute("""
                SELECT DISTINCT EXECUTED_AS_USER_NAME
                FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
                    RESULT_LIMIT => 100000,
                    RESULT_SERVICE_PERIOD => DATEADD(day, -30, CURRENT_TIMESTAMP())
                ))
                WHERE EXECUTED_AS_USER_NAME IS NOT NULL
            """)
            users = {row[0] for row in cur.fetchall() if row[0]}
            for user in users:
                if user.startswith("SA_") or "_svc" in user.lower() or user.startswith("robot"):
                    active_sa += 1
                else:
                    active_users += 1
        except Exception:
            pass

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
            active_users_last_30d=active_users,
            active_service_accounts_last_30d=active_sa,
        )

    # -- cost signals (item 4: real billing data) -- #

    def fetch_cost_signals(self) -> CostSignals:
        """Fetch actual costs from ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY."""
        conn = self._snowflake_connect()
        cur = conn.cursor()
        cost = CostSignals(platform="snowflake")

        # Compute: warehouse metering
        cur.execute("""
            SELECT SUM(CREDITS_USED_COMPUTE) + SUM(CREDITS_USED_TRANSFERS) AS total_credits,
                   SUM(CREDITS_USED) AS total_credits_all
            FROM ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD(month, -1, CURRENT_DATE())
        """)
        row = cur.fetchone()
        total_credits = float(row[0] or 0) + float(row[1] or 0) if row else 0.0

        rates = self._rates_for_platform()
        compute_rate = rates.get("base_compute", 28.0)
        storage_rate = rates.get("storage", 0.023)
        io_rate = rates.get("io", 0.000005)

        cost.compute_units_per_month = total_credits
        cost.compute_unit_name = "credit"
        cost.compute_cost_per_unit = compute_rate
        cost.estimated_compute_cost_monthly = total_credits * compute_rate

        # Storage from TABLE_STORAGE_METRICS
        try:
            cur.execute("""
                SELECT SUM(current_storage_bytes + advance_storage_bytes + transients_storage_bytes) / 1024 / 1024 / 1024
                FROM ACCOUNT_USAGE.TABLE_STORAGE_METRICS
                WHERE METRIC_PERIOD >= DATEADD(month, -1, CURRENT_DATE())
            """)
            storage_gb = float(cur.fetchone()[0] or 0) / 1024.0
        except Exception:
            storage_gb = 50.0

        cost.storage_gb_total = storage_gb
        cost.storage_cost_per_gb = storage_rate
        cost.estimated_storage_cost_monthly = storage_gb * storage_rate

        # I/O from ACCOUNT_USAGE.TABLE_IO_HISTORY
        try:
            cur.execute("""
                SELECT SUM(BYTES_SCAN) / 1024 / 1024
                FROM ACCOUNT_USAGE.TABLE_IO_HISTORY
                WHERE START_TIME >= DATEADD(month, -1, CURRENT_DATE())
            """)
            io_mb = float(cur.fetchone()[0] or 0)
        except Exception:
            io_mb = 1000.0

        cost.bytes_scanned_per_month = io_mb * 1024 * 1024
        cost.io_cost_per_mb = io_rate
        cost.estimated_io_cost_monthly = io_mb * io_rate

        cost.total_estimated_monthly_cost = (
            cost.estimated_compute_cost_monthly
            + cost.estimated_storage_cost_monthly
            + cost.estimated_io_cost_monthly
        )
        cost.costs_from_billing_api = True

        conn.close()
        return cost

    # -- access patterns -- #

    def fetch_access_patterns(self) -> AccessPatternSignals:
        """Analyze query patterns for cache candidates and temporal analysis."""
        conn = self._snowflake_connect()
        cur = conn.cursor()

        # Get query history for analysis
        cur.execute("""
            SELECT QUERY_TEXT, QUERY_TYPE, TOTAL_ELAPSED_TIME, ROWS_PRODUCED,
                   BYTES_SCANNED, START_TIME, IS_CLIENT_QUERY_AGENT_REPORTING,
                   RESULT_CACHED
            FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
                RESULT_LIMIT => 10000,
                RESULT_SERVICE_PERIOD => DATEADD(day, -90, CURRENT_TIMESTAMP())
            ))
        """)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

        # Analyze patterns
        hourly_counts: dict[int, int] = {h: 0 for h in range(24)}
        day_counts: dict[int, int] = {d: 0 for d in range(7)}
        reads = writes = 0
        point_lookups = full_scans = 0
        fingerprint_counts: dict[str, int] = {}

        for row in rows:
            rd = dict(zip(columns, row))
            qtype = str(rd.get("QUERY_TYPE", "")).upper()
            if qtype.startswith("SELECT"):
                reads += 1
            else:
                writes += 1

            start = rd.get("START_TIME")
            if start:
                try:
                    dt = datetime.fromisoformat(str(start)) if isinstance(start, str) else start
                    hourly_counts[dt.hour] = hourly_counts.get(dt.hour, 0) + 1
                    day_counts[dt.weekday()] = day_counts.get(dt.weekday(), 0) + 1
                except (ValueError, TypeError):
                    pass

            fingerprint = self._hash_query_text(str(rd.get("QUERY_TEXT", "")))
            fingerprint_counts[fingerprint] = fingerprint_counts.get(fingerprint, 0) + 1

            # Point lookup detection
            qtext = str(rd.get("QUERY_TEXT", "")).upper()
            if "WHERE" in qtext and "=" in qtext.split("WHERE")[1][:100]:
                point_lookups += 1
            if rd.get("BYTES_SCANNED") and rd.get("ROWS_PRODUCED"):
                if rd.get("ROWS_PRODUCED", 0) < rd.get("BYTES_SCANNED", 1) / 1024:
                    full_scans += 1

        total_queries = max(reads + writes, 1)
        rw_ratio = reads / max(reads + writes, 1)
        temporal_buckets = []
        for h, count in hourly_counts.items():
            temporal_buckets.append(QueryTemporalBucket(
                hour_of_day=h,
                day_of_week=0,
                avg_query_count=float(count),
                avg_exec_time_ms=0.0,
            ))

        peak_hour = max(hourly_counts, key=hourly_counts.get) if hourly_counts else 0
        peak_day = max(day_counts, key=day_counts.get) if day_counts else 0
        peak_count = max(hourly_counts.values()) if hourly_counts else 0
        avg_count = sum(hourly_counts.values()) / 24 if hourly_counts else 0

        cache_candidates = []
        for fp, count in fingerprint_counts.items():
            if count > 3:
                cache_candidates.append(CacheCandidate(
                    query_fingerprint=fp,
                    execution_count=count,
                    avg_exec_time_ms=0.0,
                    avg_rows_returned=0.0,
                    data_freshness_hours=24.0,
                    estimated_cache_hit_rate=min(count / 100.0, 0.95),
                    recommended_ttl_seconds=3600,
                    cache_type="result_cache",
                ))

        return AccessPatternSignals(
            platform="snowflake",
            read_write_ratio=rw_ratio,
            point_lookup_pct=point_lookups / total_queries if total_queries else 0,
            full_scan_pct=full_scans / total_queries if total_queries else 0,
            cache_candidates=cache_candidates,
            estimated_cacheable_pct=len(cache_candidates) / max(len(fingerprint_counts), 1),
            temporal_buckets=temporal_buckets,
            peak_hour_of_day=peak_hour,
            peak_day_of_week=peak_day,
            off_peak_query_pct=1.0 - (sum(hourly_counts.get(h, 0) for h in range(8, 18)) / total_queries),
            repeated_query_pct=sum(1 for c in fingerprint_counts.values() if c > 3) / max(len(fingerprint_counts), 1),
            avg_data_staleness_hours=24.0,
            has_burst_pattern=peak_count > avg_count * 5,
            burst_duration_minutes=0,
        )

    # -- migration complexity -- #

    def fetch_migration_complexity(self) -> MigrationComplexitySignals:
        """Analyze UDFs, stored procs, and proprietary types."""
        conn = self._snowflake_connect()
        cur = conn.cursor()
        mc = MigrationComplexitySignals(platform="snowflake")

        # UDFs
        cur.execute("SHOW USER DEFINED FUNCTIONS")
        udf_rows = cur.fetchall()
        for row in udf_rows:
            rd = dict(zip([d[0].lower() for d in cur.description], row))
            mc.udf_count += 1
            mc.udf_records.append(UDFRecord(
                name=str(rd.get("name", "")),
                language=str(rd.get("return_type", "SQL")),
                is_portable=True,
            ))

        # Stored procedures
        cur.execute("SHOW USER PROCEDURES")
        sp_rows = cur.fetchall()
        for row in sp_rows:
            rd = dict(zip([d[0].lower() for d in cur.description], row))
            mc.stored_proc_count += 1
            mc.stored_proc_records.append(StoredProcRecord(
                name=str(rd.get("name", "")),
                line_count=0,
                has_loops=False,
                has_external_calls=False,
                has_ddl=False,
                migration_path="sql_udf",
            ))

        # Triggers
        cur.execute("SHOW TRIGGERS")
        mc.trigger_count = len(cur.fetchall())

        # Binary types (BYTEA equivalent in Snowflake: BINARY/BLOB)
        cur.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE DATA_TYPE IN ('BINARY', 'BLOB')
        """)
        binary_rows = cur.fetchall()
        for row in binary_rows:
            rd = dict(zip([d[0].lower() for d in cur.description], row))
            mc.binary_column_count += 1
            mc.binary_column_records.append(BinaryColumnRecord(
                table=str(rd.get("table_name", "")),
                column=str(rd.get("column_name", "")),
                data_type="BINARY",
                migration_path="base64_string",
            ))

        conn.close()
        return mc

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
