"""MySQL / MariaDB connector - query history, metadata, concurrency, security."""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.cost_signals import CostSignals
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class MySQLConnector(AbstractBaseConnector):
    platform_name = "mysql"
    platform_display_name = "MySQL / MariaDB"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    # -- credentials -- #

    def validate_credentials(self) -> bool:
        host = self._kwargs.get("mysql_host")
        user = self._kwargs.get("mysql_user")
        if not host or not user:
            raise ValueError("MySQL: MYSQL_HOST and MYSQL_USER are required.")

        try:
            import mysql.connector as mysql
        except ImportError:
            try:
                import pymysql as mysql
            except ImportError:
                raise ImportError(
                    "mysql-connector-python or PyMySQL is required. "
                    "Install with: pip install mysql-connector-python"
                )

        conn_kwargs = {
            "host": host,
            "user": user,
            "port": int(self._kwargs.get("mysql_port", 3306)),
            "database": self._kwargs.get("mysql_database"),
        }
        pw = self._kwargs.get("mysql_password")
        if pw:
            conn_kwargs["password"] = pw

        ssl_ca = self._kwargs.get("mysql_ssl_ca")
        ssl_cert = self._kwargs.get("mysql_ssl_cert")
        ssl_key = self._kwargs.get("mysql_ssl_key")
        if ssl_ca:
            conn_kwargs["ssl_ca"] = ssl_ca
        if ssl_cert:
            conn_kwargs["ssl_cert"] = ssl_cert
        if ssl_key:
            conn_kwargs["ssl_key"] = ssl_key

        conn = None
        try:
            conn = mysql.connect(**conn_kwargs)
            conn.cursor().execute("SELECT 1")
            return True
        except (mysql.Error, mysql.connector.Error if 'mysql.connector' in str(mysql) else Exception) as e:
            raise ConnectionError(f"MySQL connection failed: {e}")
        finally:
            if conn:
                conn.close()

    # -- platform detection -- #

    def _is_mariadb(self) -> bool:
        """Detect if the connected server is MariaDB."""
        conn = self._mysql_connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT VERSION()")
            version = str(cur.fetchone()[0]).lower()
            return "mariadb" in version or "maria" in version
        finally:
            conn.close()

    # -- query history -- #

    def fetch_query_history(self) -> QueryHistory:
        """Fetch query history via performance_schema or fallbacks.

        Priority:
        1. performance_schema.events_statements_summary_by_digest (aggregated per pattern)
        2. performance_schema.events_statements_history_long (last ~10K)
        3. Warn user to enable slow query log
        """
        conn = self._mysql_connect()
        cur = conn.cursor()

        # Try performance_schema.events_statements_summary_by_digest first
        try:
            cur.execute("SELECT 1 FROM performance_schema.events_statements_summary_by_digest LIMIT 1")
            is_digest_available = True
        except Exception:
            is_digest_available = False

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        date_start: datetime | None = None
        date_end: datetime | None = None

        if is_digest_available:
            cur.execute("""
                SELECT
                    DIGEST_TEXT,
                    SCHEMA_NAME,
                    COUNT_STAR,
                    SUM_TIMER_WAIT / 1e12 * 1000  AS total_exec_ms,
                    MIN_TIMER_WAIT / 1e12 * 1000  AS min_exec_ms,
                    MAX_TIMER_WAIT / 1e12 * 1000  AS max_exec_ms,
                    SUM_ROWS_EXAMINED,
                    SUM_ROWS_SENT,
                    SUM_NO_GOOD_INDEX_USED,
                    SUM_NO_INDEX_USED,
                    FIRST_SEEN,
                    LAST_SEEN
                FROM performance_schema.events_statements_summary_by_digest
                WHERE SCHEMA_NAME NOT IN ('performance_schema','information_schema','mysql','sys')
                ORDER BY COUNT_STAR DESC
                LIMIT 5000
            """)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            for row in rows:
                rd = dict(zip(columns, row))
                qtext = str(rd.get("DIGEST_TEXT", "") or "")
                qf = self._detect_pii_in_fingerprint(qtext)
                fingerprint = self._hash_query_text(qf)

                try:
                    first = datetime.fromisoformat(str(rd.get("FIRST_SEEN", ""))) if rd.get("FIRST_SEEN") else None
                    last = datetime.fromisoformat(str(rd.get("LAST_SEEN", ""))) if rd.get("LAST_SEEN") else None
                except (ValueError, TypeError):
                    first = last = None

                if first:
                    if date_start is None or first < date_start:
                        date_start = first
                    if date_end is None or (last and last > date_end):
                        date_end = last

                query_type = self._classify_query(qtext)
                schema = str(rd.get("SCHEMA_NAME", "") or "")
                databases.add(schema)

                queries.append(QueryRecord(
                    query_id=str(hash(qf))[:16] or f"mysql_digest_{hash(qf) % 10**9}",
                    database=schema,
                    schema_name=schema,
                    query_text_fingerprint=fingerprint,
                    query_type=query_type,
                    avg_exec_time_ms=self._safe_float(rd.get("total_exec_ms")) and self._safe_float(rd.get("total_exec_ms")) / max(rd.get("COUNT_STAR", 1), 1),
                    min_exec_time_ms=self._safe_float(rd.get("min_exec_ms")),
                    max_exec_time_ms=self._safe_float(rd.get("max_exec_ms")),
                    total_executions=self._safe_int(rd.get("COUNT_STAR")),
                    avg_rows_returned=self._safe_float(rd.get("SUM_ROWS_SENT")),
                    avg_bytes_scanned=self._safe_float(rd.get("SUM_ROWS_EXAMINED")) and self._safe_float(rd.get("SUM_ROWS_EXAMINED")) * 50.0,
                    last_executed=last,
                    first_executed=first,
                    has_udf="UDF" in qf.upper() or "FUNCTION" in qf.upper(),
                    has_stored_procedure="PROCEDURE" in qf.upper() or "CALL" in qtext[:10].upper(),
                    is_write=query_type in ("INSERT", "UPDATE", "DELETE", "MERGE"),
                    is_point_lookup=self._is_point_lookup(qtext),
                    is_full_scan=bool(rd.get("SUM_NO_INDEX_USED", 0)) and rd.get("SUM_NO_INDEX_USED", 0) > 0,
                    user_type=self._detect_user_type(qtext),
                ))

        else:
            # Fallback: events_statements_history_long
            try:
                cur.execute("""
                    SELECT
                        EVENT_ID,
                        DIGEST_TEXT,
                        SCHEMA_NAME,
                        TIMER_WAIT / 1e12 * 1000 AS exec_ms,
                        ROWS_EXAMINED,
                        ROWS_SENT,
                        FIRST_SEEN,
                        LAST_SEEN
                    FROM performance_schema.events_statements_history_long
                    WHERE SCHEMA_NAME NOT IN ('performance_schema','information_schema','mysql','sys')
                    ORDER BY FIRST_SEEN DESC
                    LIMIT 10000
                """)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]

                for row in rows:
                    rd = dict(zip(columns, row))
                    qtext = str(rd.get("DIGEST_TEXT", "") or "")
                    qf = self._detect_pii_in_fingerprint(qtext)
                    fingerprint = self._hash_query_text(qf)

                    first = last = None
                    try:
                        first = datetime.fromisoformat(str(rd.get("FIRST_SEEN", ""))) if rd.get("FIRST_SEEN") else None
                        last = datetime.fromisoformat(str(rd.get("LAST_SEEN", ""))) if rd.get("LAST_SEEN", "") else None
                    except (ValueError, TypeError):
                        pass

                    schema = str(rd.get("SCHEMA_NAME", "") or "")
                    databases.add(schema)

                    queries.append(QueryRecord(
                        query_id=str(rd.get("EVENT_ID", "")) or f"mysql_hist_{hash(qf) % 10**9}",
                        database=schema,
                        schema_name=schema,
                        query_text_fingerprint=fingerprint,
                        query_type=self._classify_query(qtext),
                        avg_exec_time_ms=self._safe_float(rd.get("exec_ms")),
                        total_executions=1,
                        avg_rows_returned=self._safe_float(rd.get("ROWS_SENT")),
                        avg_bytes_scanned=self._safe_float(rd.get("ROWS_EXAMINED")) and self._safe_float(rd.get("ROWS_EXAMINED")) * 50.0,
                        last_executed=last,
                        first_executed=first,
                        has_udf="UDF" in qf.upper(),
                        user_type=self._detect_user_type(qtext),
                    ))
            except Exception:
                logger.warning(
                    "MySQL: performance_schema not available. "
                    "Enable slow_query_log and point the assessor at the log file for cost analysis."
                )

        conn.close()
        return QueryHistory(
            platform="mysql",
            queries=queries,
            total_queries_fetched=len(rows) if rows else 0,
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=[],
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    # -- table metadata -- #

    def fetch_table_metadata(self) -> TableMetadataCollection:
        """Fetch from information_schema.TABLES + COLUMNS."""
        conn = self._mysql_connect()
        cur = conn.cursor()

        cur.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, TABLE_ROWS, DATA_LENGTH,
                   INDEX_LENGTH, CREATE_TIME, UPDATE_TIME, ENGINE
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema','performance_schema','mysql','sys')
        """)
        table_rows = cur.fetchall()
        table_columns = [desc[0] for desc in cur.description]

        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        for row in table_rows:
            rd = dict(zip(table_columns, row))
            table_name = str(rd.get("TABLE_NAME", ""))
            schema_name = str(rd.get("TABLE_SCHEMA", ""))
            dbs.add(schema_name)
            schemas.add(schema_name)

            last_altered = None
            update_time = rd.get("UPDATE_TIME")
            if update_time:
                try:
                    last_altered = datetime.fromisoformat(str(update_time)) if isinstance(update_time, str) else update_time
                except (ValueError, TypeError):
                    pass

            t = TableMetadata(
                database=schema_name,
                schema_name=schema_name,
                table_name=table_name,
                table_type=str(rd.get("TABLE_TYPE", "TABLE")).upper(),
                row_count=self._safe_int(rd.get("TABLE_ROWS")),
                storage_size_bytes=self._safe_int(rd.get("DATA_LENGTH")) or self._safe_int(rd.get("INDEX_LENGTH")),
                last_analyzed=last_altered,
                is_stale_stats=False,  # MySQL doesn't provide auto-analyze timestamps
                is_sensitive="pii" in table_name.lower() or "sensitive" in table_name.lower(),
            )
            tables.append(t)

        # Fetch column info
        cur.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                   COLUMN_KEY, COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA NOT IN ('information_schema','performance_schema','mysql','sys')
        """)
        col_rows = cur.fetchall()
        col_columns = [desc[0].lower() for desc in cur.description]

        for row in col_rows:
            crd = dict(zip(col_columns, row))
            table_name = str(crd.get("table_name", ""))
            schema_name = str(crd.get("table_schema", ""))
            for t in tables:
                if t.table_name == table_name and t.database == schema_name:
                    t.columns.append(
                        type(t.columns[0])() if t.columns else type(t.columns).__bases__[0]().__class__(
                            name=str(crd.get("column_name", "")),
                            data_type=str(crd.get("data_type", "")),
                            is_nullable=str(crd.get("is_nullable", "YES")) == "YES",
                            is_primary_key=str(crd.get("column_key", "")) == "PRI",
                        )
                    )

        conn.close()
        return TableMetadataCollection(
            platform="mysql",
            tables=tables,
            total_tables_fetched=len(table_rows),
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    # -- concurrency signals -- #

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        """Fetch from SHOW STATUS and information_schema.PROCESSLIST."""
        conn = self._mysql_connect()
        cur = conn.cursor()

        snapshots: list[ConcurrencySnapshot] = []

        # Threads info
        cur.execute("SHOW STATUS LIKE 'Threads%'")
        threads_rows = cur.fetchall()
        threads_map = {r[0]: r[1] for r in threads_rows}

        # Questions counter
        cur.execute("SHOW STATUS LIKE 'Questions'")
        questions = cur.fetchone()
        total_questions = int(questions[1]) if questions else 0

        # Processlist for active connections
        cur.execute("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE COMMAND != 'Sleep'")
        active_conns = cur.fetchone()[0]

        conn.close()

        # Build a single snapshot
        active = active_conns
        snapshots.append(ConcurrencySnapshot(
            timestamp=datetime.now().isoformat(),
            active_sessions=active,
            queued_queries=0,  # MySQL doesn't expose queue depth directly
            avg_wait_time_ms=None,
        ))

        return ConcurrencySignals(
            platform="mysql",
            snapshots=snapshots,
            avg_concurrent_queries=float(active),
            peak_concurrent_queries=active,
            scaling_pressure="high" if active > 50 else ("medium" if active > 20 else "low"),
        )

    # -- security patterns -- #

    def fetch_security_patterns(self) -> SecurityPatterns:
        """Check user privileges, grants, and encryption."""
        conn = self._mysql_connect()
        cur = conn.cursor()
        findings: list[SecurityFinding] = []

        # Check user privileges
        cur.execute("SELECT * FROM information_schema.USER_PRIVILEGES WHERE grantee != 'DEFINER'")
        priv_rows = cur.fetchall()
        has_grants = len(priv_rows) > 0

        # Check current user grants
        cur.execute("SHOW GRANTS FOR CURRENT_USER()")
        grants = cur.fetchall()

        # Check SSL / secure transport
        cur.execute("SHOW VARIABLES LIKE 'require_secure_transport'")
        ssl_row = cur.fetchone()
        require_ssl = ssl_row and "ON" in str(ssl_row[1]) if ssl_row else False

        # Check encryption
        cur.execute("SHOW VARIABLES LIKE 'innodb_encrypt_tables'")
        enc_row = cur.fetchone()
        encryption_at_rest = enc_row and "ON" in str(enc_row[1]) if enc_row else False

        if not has_grants:
            findings.append(SecurityFinding(
                category="RBAC", severity="high",
                description="Limited privilege granularity. All users may have broad access.",
                remediation="Implement least-privilege grants with per-database permissions.",
            ))
        if not require_ssl:
            findings.append(SecurityFinding(
                category="ENCRYPTION", severity="medium",
                description="TLS not required for all connections.",
                remediation="Set require_secure_transport=ON and configure SSL certificates.",
            ))
        if not encryption_at_rest:
            findings.append(SecurityFinding(
                category="ENCRYPTION", severity="medium",
                description="Innodb encryption may not be enabled.",
                remediation="Enable InnoDB tablespace encryption for sensitive data at rest.",
            ))

        # MariaDB-specific checks
        if self._is_mariadb():
            cur.execute("SELECT PLUGIN_NAME, PLUGIN_STATUS FROM information_schema.ALL_PLUGINS WHERE PLUGIN_TYPE='AUDIT' AND PLUGIN_STATUS='ACTIVE'")
            audit_plugins = cur.fetchall()
            if not audit_plugins:
                findings.append(SecurityFinding(
                    category="AUDIT", severity="high",
                    description="No active MariaDB audit plugin detected.",
                    remediation="Install and enable an audit plugin (e.g., server_audit).",
                ))

        conn.close()

        return SecurityPatterns(
            platform="mysql",
            findings=findings,
            rbac_enabled=has_grants,
            encryption_at_rest=encryption_at_rest,
            encryption_in_transit=require_ssl,
            audit_logging_enabled=False,
            total_findings=len(findings),
            high_severity_count=sum(1 for f in findings if f.severity == "high"),
            critical_severity_count=sum(1 for f in findings if f.severity == "critical"),
        )

    # -- cost signals -- #

    def fetch_cost_signals(self) -> CostSignals:
        """Estimate costs since MySQL has no billing API.

        Uses query volume + hosting cost as proxy.
        """
        conn = self._mysql_connect()
        cur = conn.cursor()

        # Get table storage
        cur.execute("""
            SELECT SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024 / 1024 AS storage_gb
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema','performance_schema','mysql','sys')
        """)
        storage_gb = float(cur.fetchone()[0] or 0)

        # Get query volume from performance_schema if available
        try:
            cur.execute("SELECT SUM(COUNT_STAR) FROM performance_schema.events_statements_summary_by_digest")
            total_queries = int(cur.fetchone()[0] or 0)
        except Exception:
            total_queries = 0

        # Estimate based on hosting type
        is_cloud = any(kw in self._kwargs for kw in ("mysql_aws_rds", "mysql_azure_mysql", "mysql_gcp_cloudsql"))
        if is_cloud:
            compute_cost_monthly = storage_gb * 0.15 + total_queries * 0.0001
        else:
            # Self-hosted estimate
            compute_cost_monthly = storage_gb * 0.02 + 500.0  # base VM cost

        has_license = "enterprise" in str(self._kwargs.get("mysql_edition", "")).lower()
        license_cost = 0.0
        license_type = "community"
        if has_license:
            license_type = "enterprise"
            license_cost = 10000.0 / 12.0  # amortized

        total = compute_cost_monthly + storage_gb * 0.02 + license_cost

        conn.close()

        return CostSignals(
            platform="mysql",
            compute_units_per_month=total_queries,
            compute_unit_name="query-hr (estimated)",
            compute_cost_per_unit=0.0,
            estimated_compute_cost_monthly=compute_cost_monthly,
            storage_gb_total=storage_gb,
            storage_cost_per_gb=0.02,
            estimated_storage_cost_monthly=storage_gb * 0.02,
            bytes_scanned_per_month=0.0,
            io_cost_per_mb=0.0,
            estimated_io_cost_monthly=0.0,
            has_license_cost=has_license,
            license_type=license_type,
            estimated_license_cost_monthly=license_cost,
            total_estimated_monthly_cost=total,
            cost_per_query=total / max(total_queries, 1),
            cost_per_gb_scanned=0.0,
            costs_from_billing_api=False,
        )

    # -- helpers -- #

    def _mysql_connect(self):
        import mysql.connector as mysql
        conn_kwargs = {
            "host": self._kwargs.get("mysql_host", ""),
            "user": self._kwargs.get("mysql_user", ""),
            "port": int(self._kwargs.get("mysql_port", 3306)),
        }
        pw = self._kwargs.get("mysql_password")
        if pw:
            conn_kwargs["password"] = pw
        db = self._kwargs.get("mysql_database")
        if db:
            conn_kwargs["database"] = db

        ssl_ca = self._kwargs.get("mysql_ssl_ca")
        if ssl_ca:
            conn_kwargs["ssl_ca"] = ssl_ca
        ssl_cert = self._kwargs.get("mysql_ssl_cert")
        if ssl_cert:
            conn_kwargs["ssl_cert"] = ssl_cert
        ssl_key = self._kwargs.get("mysql_ssl_key")
        if ssl_key:
            conn_kwargs["ssl_key"] = ssl_key

        conn = mysql.connect(**conn_kwargs)
        self._connected = True
        return conn

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
        if any(q_upper.startswith(kw) for kw in ("CREATE", "DROP", "ALTER", "TRUNCATE")):
            return "DDL"
        return "OTHER"

    @staticmethod
    def _is_point_lookup(q: str) -> bool:
        """Detect WHERE primary_key = ? patterns."""
        import re
        patterns = [
            r"WHERE\s+\w+\s*=\s*\?",
            r"WHERE\s+\w+_id\s*=\s*\?",
            r"WHERE\s+id\s*=\s*\?",
        ]
        return any(re.search(p, q, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _detect_user_type(q: str) -> str:
        """Heuristic: detect query origin from pattern."""
        import re
        if re.search(r"(?i)(service[_-]?account|app[_-]?user|api[_-]?key)", q):
            return "app_service_account"
        if re.search(r"(?i)(ETL|etl|batch|cron|scheduled)", q):
            return "etl_job"
        if re.search(r"(?i)(administrator|admin|root)", q):
            return "admin"
        return ""
