"""Tests for DatabricksConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.databricks import DatabricksConnector


class TestDatabricksValidateCredentials:
    def test_raises_without_host(self):
        conn = DatabricksConnector()
        with pytest.raises(ValueError, match="DATABRICKS_HOST"):
            conn.validate_credentials()

    def test_raises_without_token(self):
        conn = DatabricksConnector(databricks_host="my.databricks.com")
        with pytest.raises(ValueError, match="DATABRICKS_TOKEN"):
            conn.validate_credentials()

    def test_raises_on_non_200_response(self):
        conn = DatabricksConnector(databricks_host="my.databricks.com", databricks_token="tok")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(ConnectionError):
                conn.validate_credentials()

    def test_succeeds_on_200(self):
        conn = DatabricksConnector(databricks_host="my.databricks.com", databricks_token="tok")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp):
            assert conn.validate_credentials() is True


class TestDatabricksClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT * FROM t", "SELECT"),
        ("select 1", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("MERGE INTO t USING s ON t.id=s.id", "MERGE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("DROP TABLE t", "DDL"),
        ("ALTER TABLE t ADD COLUMN x INT", "DDL"),
        ("CALL my_proc()", "OTHER"),
        ("", "OTHER"),
    ])
    def test_classify(self, query, expected):
        assert DatabricksConnector._classify_databricks_query(query) == expected


class TestDatabricksIsPointLookup:
    def test_with_numeric_literal(self):
        assert DatabricksConnector._is_point_lookup("SELECT * FROM t WHERE id=123") is True

    def test_with_string_literal(self):
        assert DatabricksConnector._is_point_lookup("SELECT * FROM t WHERE name='Alice'") is True

    def test_without_where_clause(self):
        assert DatabricksConnector._is_point_lookup("SELECT * FROM t") is False

    def test_range_query_not_point_lookup(self):
        assert DatabricksConnector._is_point_lookup("SELECT * FROM t WHERE id > 100") is False


class TestDatabricksDetectUserType:
    def test_service_account(self):
        assert DatabricksConnector._detect_user_type("my-service") == "app_service_account"

    def test_app_user(self):
        assert DatabricksConnector._detect_user_type("app_backend") == "app_service_account"

    def test_bot(self):
        assert DatabricksConnector._detect_user_type("my_bot") == "app_service_account"

    def test_api_user(self):
        assert DatabricksConnector._detect_user_type("api_gateway") == "app_service_account"

    def test_etl_job(self):
        assert DatabricksConnector._detect_user_type("etl_pipeline") == "etl_job"

    def test_workflow_user(self):
        assert DatabricksConnector._detect_user_type("workflow_runner") == "etl_job"

    def test_regular_user(self):
        assert DatabricksConnector._detect_user_type("john.doe@company.com") == ""


class TestDatabricksRunSql:
    def test_returns_empty_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("requests.post", return_value=mock_resp):
            result = DatabricksConnector._run_sql("host", "tok", None, "SELECT 1", {})
        assert result == []

    def test_returns_empty_on_failed_state(self):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "statement_id": "stmt1",
            "status": {"state": "FAILED"},
        }
        with patch("requests.post", return_value=mock_post_resp):
            result = DatabricksConnector._run_sql("host", "tok", None, "SELECT 1", {})
        assert result == []

    def test_returns_data_on_success(self):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "statement_id": "stmt1",
            "status": {"state": "SUCCEEDED"},
            "result": {"data_array": [["row1col1", "row1col2"]]},
        }
        with patch("requests.post", return_value=mock_post_resp):
            result = DatabricksConnector._run_sql("host", "tok", None, "SELECT 1", {})
        assert result == [["row1col1", "row1col2"]]

    def test_polls_until_complete(self):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "statement_id": "s1",
            "status": {"state": "PENDING"},
            "result": {},
        }
        mock_poll_resp = MagicMock()
        mock_poll_resp.status_code = 200
        mock_poll_resp.json.return_value = {
            "status": {"state": "SUCCEEDED"},
            "result": {"data_array": [["r1"]]},
        }
        with patch("requests.post", return_value=mock_post_resp):
            with patch("requests.get", return_value=mock_poll_resp):
                with patch("time.sleep"):
                    result = DatabricksConnector._run_sql("host", "tok", "wh1", "SELECT 1", {})
        assert result == [["r1"]]


class TestDatabricksFetchConcurrencySignals:
    def test_low_pressure_with_few_clusters(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "clusters": [
                {"state": "RUNNING"},
                {"state": "TERMINATED"},
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            cs = conn.fetch_concurrency_signals()
        assert cs.scaling_pressure == "low"
        assert cs.avg_concurrent_queries == 1.0

    def test_high_pressure_with_many_clusters(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "clusters": [{"state": "RUNNING"}] * 15
        }
        with patch("requests.get", return_value=mock_resp):
            cs = conn.fetch_concurrency_signals()
        assert cs.scaling_pressure == "high"

    def test_failed_request_returns_zero(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("requests.get", return_value=mock_resp):
            cs = conn.fetch_concurrency_signals()
        assert cs.avg_concurrent_queries == 0.0


class TestDatabricksFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        with patch.object(conn, "_run_sql", return_value=[]):
            sp = conn.fetch_security_patterns()
        assert sp.platform == "databricks"
        assert sp.rbac_enabled is True
        assert sp.encryption_at_rest is True

    def test_counts_active_users(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        with patch.object(conn, "_run_sql", return_value=[
            ("john.doe@company.com",),
            ("sa_etl_pipeline",),
            ("alice@company.com",),
        ]):
            sp = conn.fetch_security_patterns()
        assert sp.active_users_last_30d == 2
        assert sp.active_service_accounts_last_30d == 1


class TestDatabricksFetchJobTimeline:
    def test_empty_rows_returns_empty_timeline(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        with patch.object(conn, "_run_sql", return_value=[]):
            jt = conn.fetch_job_timeline()
        assert jt.platform == "databricks"
        assert jt.jobs == []

    def test_computes_job_stats(self):
        conn = DatabricksConnector(databricks_host="host", databricks_token="tok")
        rows = [
            ("job1", "ETL Job", "run1", "SUCCESS", "2026-04-01", "2026-04-01",
             3600, "CRON", "NEW_CLUSTER", 5, 0),
            ("job1", "ETL Job", "run2", "FAILED", "2026-04-02", "2026-04-02",
             4000, "CRON", "NEW_CLUSTER", 3, 2),
        ]
        with patch.object(conn, "_run_sql", return_value=rows):
            jt = conn.fetch_job_timeline()
        assert len(jt.jobs) == 1
        assert jt.jobs[0].job_name == "ETL Job"
        assert jt.jobs[0].failure_rate == pytest.approx(0.5)
