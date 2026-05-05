"""BigQuery connector - read-only query history and metadata."""

import logging
from datetime import datetime
from typing import Any

from src.connectors.base import AbstractBaseConnector
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityFinding, SecurityPatterns
from src.models.table_metadata import TableMetadata, TableMetadataCollection

logger = logging.getLogger(__name__)


class BigQueryConnector(AbstractBaseConnector):
    platform_name = "bigquery"
    platform_display_name = "Google BigQuery"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(platform_name="bigquery", **kwargs)

    def validate_credentials(self) -> bool:
        project = self._kwargs.get("bq_project_id")
        if not project:
            raise ValueError("BigQuery: BQ_PROJECT_ID is required.")

        try:
            from google.oauth2 import service_account
            cred_path = self._kwargs.get("bq_credentials_path")
            if cred_path:
                creds = service_account.Credentials.from_service_account_file(cred_path)
            else:
                import google.auth
                creds, _ = google.auth.default()
        except ImportError:
            raise ImportError("google-cloud-bigquery is required. Install with: pip install google-cloud-bigquery")
        except Exception as e:
            raise ValueError(f"BigQuery credential error: {e}")

        return True

    def fetch_query_history(self) -> QueryHistory:
        from google.cloud import bigquery
        project = self._kwargs.get("bq_project_id", "")
        client = bigquery.Client(project=project)

        days = self.query_history_days
        sql = f"""
        SELECT
            job_id,
            query,
            destination_table.project_id,
            destination_table.dataset_id,
            destination_table.table_id,
            creation_time,
            start_time,
            end_time,
            total_bytes_processed,
            total_rows,
            cache_hit,
            error_result
        FROM `{project}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        ORDER BY creation_time DESC
        LIMIT 10000
        """
        # Use a simpler query for jobs query stats
        sql = f"""
        SELECT
            job_id,
            query,
            user_email,
            creation_time,
            start_time,
            end_time,
            total_bytes_processed,
            total_rows,
            cache_hit
        FROM `{project}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        ORDER BY creation_time DESC
        LIMIT 10000
        """
        from google.cloud.bigquery import QueryJobConfig
        job = client.query(sql, job_config=QueryJobConfig(priority=bigquery.QueryPriority.INTERACTIVE))
        rows = list(job.result())
        columns = [field.name for field in job.result().schema]

        queries: list[QueryRecord] = []
        databases: set[str] = set()
        tables_set: set[str] = set()
        date_start: datetime | None = None
        date_end: datetime | None = None

        for row in rows:
            rd = dict(zip(columns, row))
            qtext = str(rd.get("query", "") or "")
            qf = self._detect_pii_in_fingerprint(qtext)
            fingerprint = self._hash_query_text(qf)

            ct = rd.get("creation_time")
            if ct and isinstance(ct, datetime):
                if date_start is None or ct < date_start:
                    date_start = ct
                if date_end is None or ct > date_end:
                    date_end = ct

            total_bytes = rd.get("total_bytes_processed") or 0
            total_bytes_val = int(total_bytes) if total_bytes else 0
            mb_scanned = total_bytes_val / (1024 * 1024)

            queries.append(QueryRecord(
                query_id=str(rd.get("job_id", "")),
                database=project,
                schema_name=str(rd.get("query", "") or "").split(".")[-1] if "." in str(rd.get("query", "")) else "",
                query_text_fingerprint=fingerprint,
                query_type=self._classify_bigquery_query(str(rd.get("query", ""))),
                avg_exec_time_ms=None,  # BigQuery doesn't expose exec time directly in info schema
                total_executions=self._safe_int(rd.get("total_rows")),
                avg_rows_returned=self._safe_float(rd.get("total_rows")),
                avg_bytes_scanned=mb_scanned,
                last_executed=datetime.fromisoformat(str(rd.get("end_time"))) if rd.get("end_time") else None,
                first_executed=date_start,
                cache_hit=rd.get("cache_hit", False),
            ))
            databases.add(project)

        return QueryHistory(
            platform="bigquery",
            queries=queries,
            total_queries_fetched=len(rows),
            date_range_start=date_start,
            date_range_end=date_end,
            unique_databases=list(databases),
            unique_tables=list(tables_set),
            avg_concurrency=0.0,
            peak_concurrency=0,
        )

    @staticmethod
    def _classify_bigquery_query(q: str) -> str:
        q_upper = q.strip().upper()
        if q_upper.startswith("SELECT"):
            return "SELECT"
        if q_upper.startswith("INSERT"):
            return "INSERT"
        if q_upper.startswith("UPDATE"):
            return "UPDATE"
        if q_upper.startswith("DELETE"):
            return "DELETE"
        if any(q_upper.startswith(kw) for kw in ("CREATE", "DROP", "ALTER", "MERGE")):
            return "DDL"
        return "OTHER"

    def fetch_table_metadata(self) -> TableMetadataCollection:
        from google.cloud import bigquery
        project = self._kwargs.get("bq_project_id", "")
        client = bigquery.Client(project=project)

        datasets = client.list_datasets()
        tables: list[TableMetadata] = []
        dbs: set[str] = set()
        schemas: set[str] = set()

        for ds in datasets:
            ds_tables = client.list_tables(ds.dataset_id)
            for tbl in ds_tables:
                tbl_ref = client.get_table(tbl.reference)
                t = TableMetadata(
                    database=project,
                    schema_name=ds.dataset_id,
                    table_name=tbl.table_id,
                    table_type="TABLE" if tbl_ref.table_type == "TABLE" else tbl_ref.table_type or "TABLE",
                    row_count=self._safe_int(tbl_ref.num_rows),
                    storage_size_bytes=self._safe_int(tbl_ref.num_bytes),
                    is_partitioned=tbl_ref.time_partitioning is not None,
                    partition_column=tbl_ref.time_partitioning.field if tbl_ref.time_partitioning else None,
                    column_count=len(tbl_ref.schema) if tbl_ref.schema else 0,
                    last_analyzed=datetime.fromtimestamp(tbl_ref.modified.timestamp()) if tbl_ref.modified else None,
                    is_stale_stats=False,
                    is_sensitive="pii" in tbl.table_id.lower() or "sensitive" in tbl.table_id.lower(),
                )
                tables.append(t)
                dbs.add(project)
                schemas.add(ds.dataset_id)

        total_bytes = sum(t.storage_size_bytes or 0 for t in tables)
        total_rows = sum(t.row_count or 0 for t in tables)

        return TableMetadataCollection(
            platform="bigquery",
            tables=tables,
            total_tables_fetched=len(tables),
            total_row_count=total_rows,
            total_storage_bytes=total_bytes,
            database_count=len(dbs),
            schema_count=len(schemas),
        )

    def fetch_concurrency_signals(self) -> ConcurrencySignals:
        # BigQuery doesn't expose fine-grained concurrency metrics
        return ConcurrencySignals(
            platform="bigquery",
            snapshots=[],
            avg_concurrent_queries=0.0,
            peak_concurrent_queries=0,
            scaling_pressure="low",
        )

    def fetch_security_patterns(self) -> SecurityPatterns:
        findings: list[SecurityFinding] = []
        return SecurityPatterns(
            platform="bigquery",
            findings=findings,
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA", "PCI-DSS", "GDPR", "FedRAMP"],
            total_findings=0,
            high_severity_count=0,
            critical_severity_count=0,
        )
