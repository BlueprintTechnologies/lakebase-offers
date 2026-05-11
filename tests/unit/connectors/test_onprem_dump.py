"""Tests for OnPremDumpConnector."""

import csv
import json
import pytest
from pathlib import Path
from src.connectors.onprem_dump import OnPremDumpConnector


class TestOnPremValidateCredentials:
    def test_raises_with_no_paths(self):
        conn = OnPremDumpConnector()
        with pytest.raises(FileNotFoundError, match="onprem_csv_path"):
            conn.validate_credentials()

    def test_raises_when_csv_not_found(self):
        conn = OnPremDumpConnector(onprem_csv_path="/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError, match="not found"):
            conn.validate_credentials()

    def test_raises_when_json_not_found(self):
        conn = OnPremDumpConnector(onprem_json_path="/nonexistent/path.json")
        with pytest.raises(FileNotFoundError, match="not found"):
            conn.validate_credentials()

    def test_succeeds_with_valid_csv_path(self, tmp_path):
        csv_file = tmp_path / "queries.csv"
        csv_file.write_text("query_id,query_text\n1,SELECT 1\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        assert conn.validate_credentials() is True

    def test_succeeds_with_valid_json_path(self, tmp_path):
        json_file = tmp_path / "queries.json"
        json_file.write_text("[]")
        conn = OnPremDumpConnector(onprem_json_path=str(json_file))
        assert conn.validate_credentials() is True


class TestOnPremFetchQueryHistoryFromCSV:
    def test_parses_csv_queries(self, tmp_path):
        csv_file = tmp_path / "queries.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "query_id", "query_text", "database", "schema",
                "query_type", "avg_exec_time_ms", "total_executions",
            ])
            writer.writeheader()
            writer.writerow({
                "query_id": "q1", "query_text": "SELECT * FROM orders",
                "database": "mydb", "schema": "public",
                "query_type": "SELECT", "avg_exec_time_ms": "100.5",
                "total_executions": "50",
            })
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        qh = conn.fetch_query_history()
        assert qh.platform == "onprem_dump"
        assert len(qh.queries) == 1
        assert qh.queries[0].database == "mydb"

    def test_parses_json_queries(self, tmp_path):
        json_file = tmp_path / "queries.json"
        data = [
            {"query_id": "q1", "query_text": "SELECT 1", "database": "prod",
             "query_type": "SELECT", "avg_exec_time_ms": 50.0, "total_executions": 10},
        ]
        json_file.write_text(json.dumps(data))
        conn = OnPremDumpConnector(onprem_json_path=str(json_file))
        qh = conn.fetch_query_history()
        assert len(qh.queries) == 1
        assert qh.queries[0].database == "prod"

    def test_empty_csv_returns_empty_history(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("query_id,query_text\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 0


class TestOnPremFetchTableMetadata:
    def test_parses_table_metadata_from_csv(self, tmp_path):
        csv_file = tmp_path / "tables.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "database", "schema", "table_name", "table_type",
                "row_count", "storage_size_bytes",
            ])
            writer.writeheader()
            writer.writerow({
                "database": "mydb", "schema": "public",
                "table_name": "orders", "table_type": "TABLE",
                "row_count": "1000000", "storage_size_bytes": "536870912",
            })
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        tm = conn.fetch_table_metadata()
        assert tm.platform == "onprem_dump"
        assert tm.total_tables_fetched == 1

    def test_parses_table_metadata_from_json(self, tmp_path):
        json_file = tmp_path / "tables.json"
        data = {"tables": [
            {"database": "prod", "schema_name": "public",
             "table_name": "users", "table_type": "TABLE",
             "row_count": 50000, "storage_size_bytes": 1024 * 1024},
        ]}
        json_file.write_text(json.dumps(data))
        conn = OnPremDumpConnector(onprem_json_path=str(json_file))
        tm = conn.fetch_table_metadata()
        assert tm.total_tables_fetched == 1


class TestOnPremFetchConcurrencySignals:
    def test_returns_unknown_pressure(self, tmp_path):
        csv_file = tmp_path / "q.csv"
        csv_file.write_text("query_id,query_text\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        cs = conn.fetch_concurrency_signals()
        assert cs.platform == "onprem_dump"
        assert cs.scaling_pressure == "unknown"


class TestOnPremFetchCostSignals:
    def test_returns_cost_signals_with_baseline(self, tmp_path):
        csv_file = tmp_path / "q.csv"
        csv_file.write_text("query_id,query_text\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        cost = conn.fetch_cost_signals()
        assert cost.platform == "onprem_dump"
        assert cost.estimated_compute_cost_monthly == 300.0
        assert cost.costs_from_billing_api is False


class TestOnPremFetchSecurityPatterns:
    def test_returns_high_severity_finding(self, tmp_path):
        csv_file = tmp_path / "q.csv"
        csv_file.write_text("query_id,query_text\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        sp = conn.fetch_security_patterns()
        assert sp.platform == "onprem_dump"
        assert sp.rbac_enabled is False
        assert sp.total_findings == 1
