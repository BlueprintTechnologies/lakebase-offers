"""Databricks connector - query history, metadata, and misuse detection."""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.cost_signals import CostSignals
from src.models.databricks_misuse import (
    DatabricksMisuseFindings,
    JobRunRecord,
    JobRunTimeline,
    MisuseFinding,
    FINDING_HIGH_FREQ_POINT_LOOKUP,
    FINDING_AGENT_STATE_DELTA_MISUSE,
    FINDING_APP_BACKEND_ON_DELTA,
    FINDING_FEATURE_STORE_LATENCY,
    FINDING_HIGH_CONCURRENCY_COST,
    FINDING_CACHING_LAYER_BYPASS,
)
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class DatabricksConnector(AbstractBaseConnector):
    platform_name = "databricks"
    platform_display_name = "Databricks"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

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

    def fetch_misuse_signals(
        self,
        caching_layers: list[str] | None = None,
    ) -> DatabricksMisuseFindings:
        """Scan Databricks workspace for the 6 canonical anti-patterns (§13).

        caching_layers: from interview_inputs.caching_layers for CACHING_LAYER_BYPASS detection.
        """
        import re
        import requests
        from collections import defaultdict

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        days = self.query_history_days
        headers = {"Authorization": f"Bearer {token}"}

        findings: list[MisuseFinding] = []

        # Fetch warehouse list (used for anti-patterns 03 and 05)
        wh_resp = requests.get(f"https://{host}/api/2.0/warehouses", headers=headers, timeout=10)
        warehouses = wh_resp.json().get("warehouses", []) if wh_resp.status_code == 200 else []

        # Fetch query history (last 7 days or configured window, max)
        from_date = (datetime.now() - timedelta(days=min(days, 7))).isoformat()
        history_sql = f"""
        SELECT
            statement_text, statement_type, read_rows, result_rows, from_result_cache,
            warehouse_id, read_bytes, start_time, end_time, total_time_ms,
            executed_as_user_name, session_id, status
        FROM system.query.history
        WHERE start_time >= TIMESTAMP '{from_date}'
        LIMIT 50000
        """
        rows_data = self._run_sql(host, token, warehouse_id, history_sql, headers)

        # Build per-fingerprint and per-user buckets
        by_fingerprint: dict[str, list[dict]] = defaultdict(list)
        by_user: dict[str, list[dict]] = defaultdict(list)
        by_hour: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        for row in rows_data:
            rd = dict(zip(
                ["statement_text", "statement_type", "read_rows", "result_rows", "from_result_cache",
                 "warehouse_id", "read_bytes", "start_time", "end_time", "total_time_ms",
                 "executed_as_user_name", "session_id", "status"],
                row,
            ))
            fp = self._hash_query_text(str(rd.get("statement_text", "") or ""))
            by_fingerprint[fp].append(rd)

            user = str(rd.get("executed_as_user_name", "") or "")
            by_user[user].append(rd)

            wh = str(rd.get("warehouse_id", "") or "")
            try:
                hour = datetime.fromisoformat(str(rd.get("start_time", "")).replace("Z", "+00:00")).hour
                by_hour[wh][hour] += 1
            except (ValueError, TypeError):
                pass

        # ── Anti-Pattern 01: High-Frequency Point Lookups ──────────────────────
        for fp, rows in by_fingerprint.items():
            sample_text = str(rows[0].get("statement_text", "") or "")
            if not re.search(r"WHERE\s+\w+\s*=\s*[0-9'\"]", sample_text, re.IGNORECASE):
                continue
            daily_count = len(rows)
            avg_result = sum(r.get("result_rows", 0) or 0 for r in rows) / max(len(rows), 1)
            avg_bytes = sum(r.get("read_bytes", 0) or 0 for r in rows) / max(len(rows), 1)
            if daily_count > 500 and avg_result < 5 and avg_bytes > 10_000_000:
                findings.append(MisuseFinding(
                    finding_type=FINDING_HIGH_FREQ_POINT_LOOKUP,
                    severity="high",
                    affected_object=fp[:32],
                    description="Single-row SELECTs running 500+ times/day against a Delta table.",
                    evidence=(
                        f"ran {daily_count} times/day, avg {avg_result:.0f} rows returned, "
                        f"avg {avg_bytes / 1_000_000:.1f}MB scanned per lookup"
                    ),
                    recommendation=(
                        "Move hot keys to Lakebase (Pro warehouse + bloom filter + liquid clustering); "
                        "sub-10ms indexed lookups."
                    ),
                    estimated_monthly_savings_dbu=daily_count * 30 * 0.001,
                ))

        # ── Anti-Pattern 02: AI Agent State Storage ─────────────────────────────
        agent_state_pattern = re.compile(
            r"\b(state|queue|session|memory|context|slot)\b", re.IGNORECASE
        )
        table_write_counts: dict[str, int] = defaultdict(int)
        for fp, rows in by_fingerprint.items():
            sample = str(rows[0].get("statement_text", "") or "")
            stmt_type = str(rows[0].get("statement_type", "") or "").upper()
            if stmt_type in ("INSERT", "MERGE", "UPDATE") and agent_state_pattern.search(sample):
                writes_per_min = len(rows) / (7 * 24 * 60)
                if writes_per_min > 100 / (24 * 60):  # > 100/min scaled
                    tbl_match = re.search(r"(?:INTO|UPDATE|MERGE\s+INTO)\s+([\w.]+)", sample, re.IGNORECASE)
                    tbl = tbl_match.group(1) if tbl_match else fp[:32]
                    findings.append(MisuseFinding(
                        finding_type=FINDING_AGENT_STATE_DELTA_MISUSE,
                        severity="high",
                        affected_object=tbl,
                        description="Table with agent-state naming pattern has high write frequency on Delta.",
                        evidence=(
                            f"table matches *state/*queue/*session pattern; "
                            f"{len(rows)} writes in 7 days"
                        ),
                        recommendation=(
                            "Use Lakebase (Pro warehouse) or Postgres for agent state; "
                            "sub-ms writes + native SEQUENCE support."
                        ),
                        estimated_monthly_savings_dbu=0.0,
                    ))

        # ── Anti-Pattern 03: App Backend Workloads ──────────────────────────────
        for user, rows in by_user.items():
            if not any(kw in user.lower() for kw in ("service", "app", "bot", "api", "svc")):
                continue
            write_count = sum(
                1 for r in rows
                if str(r.get("statement_type", "") or "").upper() in ("INSERT", "UPDATE", "DELETE", "MERGE")
            )
            write_pct = write_count / max(len(rows), 1)
            avg_write_rows = (
                sum(r.get("read_rows", 0) or 0 for r in rows if str(r.get("statement_type", "") or "").upper()
                    in ("INSERT", "UPDATE", "DELETE")) / max(write_count, 1)
            )
            if write_pct > 0.5 and write_count > 200 and avg_write_rows < 100:
                findings.append(MisuseFinding(
                    finding_type=FINDING_APP_BACKEND_ON_DELTA,
                    severity="medium",
                    affected_object=user,
                    description="Service account running transactional row-level writes against Delta tables.",
                    evidence=(
                        f"user={user}, write_pct={write_pct:.0%}, "
                        f"write_count={write_count}, avg_rows_per_write={avg_write_rows:.0f}"
                    ),
                    recommendation=(
                        "Lakebase Serverless for queries + Postgres for row-level transactional writes; "
                        "eliminate always-on cluster cost."
                    ),
                    estimated_monthly_savings_dbu=0.0,
                ))

        # ── Anti-Pattern 04: Feature Store Latency ──────────────────────────────
        feature_pattern = re.compile(r"\bfeature[s]?\b", re.IGNORECASE)
        by_table_latency: dict[str, list[float]] = defaultdict(list)
        for fp, rows in by_fingerprint.items():
            sample = str(rows[0].get("statement_text", "") or "")
            if feature_pattern.search(sample) and str(rows[0].get("statement_type", "") or "").upper() == "SELECT":
                tbl_match = re.search(r"FROM\s+([\w.]+)", sample, re.IGNORECASE)
                tbl = tbl_match.group(1) if tbl_match else fp[:32]
                for r in rows:
                    ms = r.get("total_time_ms", 0) or 0
                    by_table_latency[tbl].append(float(ms))
        for tbl, latencies in by_table_latency.items():
            if len(latencies) < 100:
                continue
            sorted_lat = sorted(latencies)
            p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
            if p99 > 50:
                findings.append(MisuseFinding(
                    finding_type=FINDING_FEATURE_STORE_LATENCY,
                    severity="high",
                    affected_object=tbl,
                    description=f"Feature table '{tbl}' P99 latency exceeds 50ms — breaks ML inference SLA.",
                    evidence=f"p99_ms={p99:.0f}, query_count={len(latencies)}",
                    recommendation=(
                        "Lakebase Pro warehouse + bloom filter for sub-ms indexed feature lookups; "
                        "keep Delta as source of truth for feature computation."
                    ),
                    estimated_monthly_savings_dbu=0.0,
                ))

        # ── Anti-Pattern 05: High-Concurrency Reading ───────────────────────────
        by_hour_table: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
        for fp, rows in by_fingerprint.items():
            sample = str(rows[0].get("statement_text", "") or "")
            tbl_match = re.search(r"FROM\s+([\w.]+)", sample, re.IGNORECASE)
            tbl = tbl_match.group(1) if tbl_match else ""
            if not tbl:
                continue
            for r in rows:
                try:
                    dt = datetime.fromisoformat(str(r.get("start_time", "")).replace("Z", "+00:00"))
                    hour_key = dt.strftime("%Y-%m-%dT%H")
                    session = str(r.get("session_id", "") or fp)
                    by_hour_table[hour_key][tbl].add(session)
                except (ValueError, TypeError):
                    pass
        for hour_key, table_sessions in by_hour_table.items():
            for tbl, sessions in table_sessions.items():
                if len(sessions) > 100:
                    findings.append(MisuseFinding(
                        finding_type=FINDING_HIGH_CONCURRENCY_COST,
                        severity="medium",
                        affected_object=tbl,
                        description=f"100+ concurrent sessions querying '{tbl}' within a 1-hour window.",
                        evidence=f"hour={hour_key}, concurrent_sessions={len(sessions)}",
                        recommendation=(
                            "Lakebase with result cache; or Postgres which handles high concurrency "
                            "natively without per-cluster scaling cost."
                        ),
                        estimated_monthly_savings_dbu=len(sessions) * 0.01,
                    ))

        # ── Anti-Pattern 06: Caching Layer Bypass ──────────────────────────────
        if caching_layers:
            # Build cache candidates from query fingerprints
            cache_candidate_fps = [
                fp for fp, rows in by_fingerprint.items()
                if len(rows) > 20 and all(not r.get("from_result_cache") for r in rows)
            ]
            if cache_candidate_fps:
                findings.append(MisuseFinding(
                    finding_type=FINDING_CACHING_LAYER_BYPASS,
                    severity="medium",
                    affected_object=", ".join(caching_layers),
                    description=(
                        f"Customer has {', '.join(caching_layers)} alongside Databricks; "
                        f"{len(cache_candidate_fps)} queries in Delta are also cache candidates — redundant infra."
                    ),
                    evidence=(
                        f"interview_inputs.caching_layers={caching_layers}, "
                        f"cache_candidate_query_count={len(cache_candidate_fps)}"
                    ),
                    recommendation=(
                        "Lakebase eliminates the cache layer — built-in result cache + Pro warehouse "
                        "handles the low-latency reads that Redis was covering."
                    ),
                    estimated_monthly_savings_dbu=0.0,
                ))

        job_timeline = self.fetch_job_timeline()

        return DatabricksMisuseFindings(
            platform="databricks",
            findings=findings,
            cache_candidate_queries=sum(1 for f in findings if f.finding_type == FINDING_HIGH_FREQ_POINT_LOOKUP),
            over_provisioned_warehouses=sum(
                1 for f in findings if f.finding_type == FINDING_APP_BACKEND_ON_DELTA
            ),
            point_lookup_on_large_delta_count=sum(
                1 for f in findings if f.finding_type == FINDING_HIGH_FREQ_POINT_LOOKUP
            ),
            total_estimated_wasted_dbu_monthly=sum(f.estimated_monthly_savings_dbu for f in findings),
            job_timeline=job_timeline,
        )

    def fetch_job_timeline(self) -> JobRunTimeline:
        """Fetch system.lakeflow.job_run_timeline (DBX Runtime 13+)."""
        import requests

        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        headers = {"Authorization": f"Bearer {token}"}

        sql = """
        SELECT
            job_id, job_name, run_id, state, start_time, end_time,
            DATEDIFF(SECOND, start_time, end_time) AS duration_seconds,
            trigger_type, cluster_type,
            tasks_succeeded, tasks_failed
        FROM system.lakeflow.job_run_timeline
        WHERE start_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
        ORDER BY start_time DESC
        """
        rows_data = self._run_sql(host, token, warehouse_id, sql, headers)

        if not rows_data:
            return JobRunTimeline(platform="databricks")

        from collections import defaultdict
        by_job: dict[str, list[dict]] = defaultdict(list)
        for row in rows_data:
            rd = dict(zip(
                ["job_id", "job_name", "run_id", "state", "start_time", "end_time",
                 "duration_seconds", "trigger_type", "cluster_type",
                 "tasks_succeeded", "tasks_failed"],
                row,
            ))
            by_job[str(rd.get("job_id", ""))].append(rd)

        jobs: list[JobRunRecord] = []
        for job_id, runs in by_job.items():
            job_name = str(runs[0].get("job_name", job_id) or job_id)
            durations = [float(r.get("duration_seconds", 0) or 0) for r in runs]
            avg_dur = sum(durations) / max(len(durations), 1)
            runs_per_day = len(runs) / 30.0
            trigger = str(runs[0].get("trigger_type", "MANUAL") or "MANUAL")
            cluster = str(runs[0].get("cluster_type", "NEW_CLUSTER") or "NEW_CLUSTER")
            failed = sum(1 for r in runs if str(r.get("state", "")).upper() in ("FAILED", "ERROR"))
            failure_rate = failed / max(len(runs), 1)
            jobs.append(JobRunRecord(
                job_name=job_name,
                avg_duration_seconds=avg_dur,
                runs_per_day=runs_per_day,
                trigger_type=trigger,
                cluster_type=cluster,
                tables_written=[],
                failure_rate=failure_rate,
            ))

        always_on = sum(
            1 for j in jobs
            if j.cluster_type == "EXISTING_CLUSTER" and j.runs_per_day < 2
        )
        over_prov = sum(1 for j in jobs if j.runs_per_day < 2 and j.avg_duration_seconds > 3600)
        high_fail = sum(1 for j in jobs if j.failure_rate > 0.1)

        return JobRunTimeline(
            platform="databricks",
            jobs=jobs,
            always_on_cluster_jobs=always_on,
            over_provisioned_jobs=over_prov,
            high_failure_rate_jobs=high_fail,
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
        host = self._kwargs.get("databricks_host", "")
        token = self._kwargs.get("databricks_token", "")
        warehouse_id = self._kwargs.get("databricks_warehouse_id")
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        findings = [
            SecurityFinding(
                category="COMPLIANCE", severity="low",
                description="Databricks has SOC2, HIPAA, PCI-DSS compliance.",
            ),
        ]

        # Count active users (item 7f)
        active_users = 0
        active_sa = 0
        try:
            from_date = (datetime.now() - timedelta(days=min(self.query_history_days, 30))).isoformat()
            rows_data = self._run_sql(
                host, token, warehouse_id,
                f"SELECT DISTINCT executed_as_user_name FROM system.query.history WHERE start_time >= TIMESTAMP '{from_date}'",
                headers,
            )
            for (user,) in rows_data:
                user = str(user or "")
                if not user:
                    continue
                if any(p in user.lower() for p in ("sa_", "_svc", "robot", "service_acct")):
                    active_sa += 1
                else:
                    active_users += 1
        except Exception:
            pass

        return SecurityPatterns(
            platform="databricks",
            findings=findings,
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS", "GDPR"],
            total_findings=1,
            high_severity_count=0,
            critical_severity_count=0,
            active_users_last_30d=active_users,
            active_service_accounts_last_30d=active_sa,
        )

    # -- helpers -- #

    @staticmethod
    def _run_sql(
        host: str,
        token: str,
        warehouse_id: str | None,
        sql: str,
        headers: dict,
    ) -> list[list]:
        """Execute SQL via Databricks SQL Statements API; poll until complete. Returns rows."""
        import requests
        import time

        payload: dict = {"statement": sql, "timeout_seconds": 60}
        if warehouse_id:
            payload["warehouse_id"] = warehouse_id

        resp = requests.post(
            f"https://{host}/api/2.1/sql/statements",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            return []

        result = resp.json()
        state = result.get("status", {}).get("state", "PENDING")
        stmt_id = result.get("statement_id", "")

        for _ in range(60):
            if state in ("SUCCEEDED", "FAILED", "CANCELED"):
                break
            time.sleep(1)
            poll = requests.get(
                f"https://{host}/api/2.1/sql/statements/{stmt_id}",
                headers=headers,
                timeout=15,
            )
            if poll.status_code == 200:
                result = poll.json()
                state = result.get("status", {}).get("state", "PENDING")

        if state != "SUCCEEDED":
            return []

        chunks = result.get("result", {}).get("data_array", [])
        return chunks if chunks else []

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
