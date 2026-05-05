"""Tests for connectors framework."""

import pytest

from src.connectors.base import AbstractBaseConnector
from src.connectors.snowflake import SnowflakeConnector
from src.connectors.redshift import RedshiftConnector
from src.connectors.bigquery import BigQueryConnector
from src.connectors.synapse import SynapseConnector
from src.connectors.postgres import PostgresConnector
from src.connectors.oracle import OracleConnector
from src.connectors.vertica import VerticaConnector
from src.connectors.teradata import TeradataConnector
from src.connectors.onprem_dump import OnPremDumpConnector


class TestBaseConnector:
    """Test AbstractBaseConnector."""

    def test_is_abstract(self):
        """Test that AbstractBaseConnector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractBaseConnector()

    def test_hash_query_text_deterministic(self):
        """Test that hashing is deterministic."""
        h1 = AbstractBaseConnector._hash_query_text("SELECT 1")
        h2 = AbstractBaseConnector._hash_query_text("SELECT 1")
        assert h1 == h2

    def test_hash_query_text_different_inputs(self):
        """Test that different inputs produce different hashes."""
        h1 = AbstractBaseConnector._hash_query_text("SELECT 1")
        h2 = AbstractBaseConnector._hash_query_text("SELECT 2")
        assert h1 != h2

    def test_detect_pii_masking(self):
        """Test PII detection in fingerprints."""
        text = "SELECT * FROM users WHERE ssn = '123-45-6789'"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert "123-45-6789" not in result

    def test_detect_pii_no_change_when_clean(self):
        """Test that clean text is unchanged."""
        text = "SELECT a, b FROM table1"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert result == text

    def test_safe_int_with_none(self):
        """Test _safe_int with None."""
        assert AbstractBaseConnector._safe_int(None, default=42) == 42

    def test_safe_int_with_valid(self):
        """Test _safe_int with valid input."""
        assert AbstractBaseConnector._safe_int("123") == 123
        assert AbstractBaseConnector._safe_int(456) == 456

    def test_safe_float_with_none(self):
        """Test _safe_float with None."""
        assert AbstractBaseConnector._safe_float(None, default=3.14) == 3.14

    def test_safe_float_with_valid(self):
        """Test _safe_float with valid input."""
        assert AbstractBaseConnector._safe_float("3.14") == 3.14


class TestConnectorRegistry:
    """Test connector factory and registry."""

    def test_all_connectors_importable(self):
        """Test that all connector classes are importable."""
        assert SnowflakeConnector is not None
        assert RedshiftConnector is not None
        assert BigQueryConnector is not None
        assert SynapseConnector is not None
        assert PostgresConnector is not None
        assert OracleConnector is not None
        assert VerticaConnector is not None
        assert TeradataConnector is not None
        assert OnPremDumpConnector is not None

    def test_connector_platform_names(self):
        """Test that all connectors have correct platform names."""
        assert SnowflakeConnector.platform_name == "snowflake"
        assert RedshiftConnector.platform_name == "redshift"
        assert BigQueryConnector.platform_name == "bigquery"
        assert SynapseConnector.platform_name == "synapse"
        assert PostgresConnector.platform_name == "postgres"
        assert OracleConnector.platform_name == "oracle"
        assert VerticaConnector.platform_name == "vertica"
        assert TeradataConnector.platform_name == "teradata"
        assert OnPremDumpConnector.platform_name == "onprem_dump"

    def test_connector_repr(self):
        """Test connector string representation."""
        sf = SnowflakeConnector()
        assert "snowflake" in repr(sf)


class TestOnPremConnector:
    """Test on-prem dump connector."""

    def test_requires_data_source(self):
        """Test that on-prem connector requires a data source."""
        conn = OnPremDumpConnector()
        with pytest.raises(FileNotFoundError):
            conn.validate_credentials()

    def test_csv_validation_with_existing_file(self, tmp_path):
        """Test validation with existing CSV file."""
        csv_file = tmp_path / "queries.csv"
        csv_file.write_text("query_id,query_text,query_type\n1,SELECT 1,SELECT\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        assert conn.validate_credentials() is True

    def test_json_validation_with_existing_file(self, tmp_path):
        """Test validation with existing JSON file."""
        json_file = tmp_path / "queries.json"
        json_file.write_text('[{"query_id": "1", "query_text": "SELECT 1", "query_type": "SELECT"}]')
        conn = OnPremDumpConnector(onprem_json_path=str(json_file))
        assert conn.validate_credentials() is True

    def test_json_parsing(self, tmp_path):
        """Test JSON query parsing."""
        json_file = tmp_path / "queries.json"
        json_file.write_text('[{"query_id": "q1", "query_text": "SELECT * FROM users", "query_type": "SELECT", "avg_exec_time_ms": 150.5, "total_executions": 100}]')
        conn = OnPremDumpConnector(onprem_json_path=str(json_file))
        conn.validate_credentials()
        qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 1
        assert qh.queries[0].query_id == "q1"
        assert qh.queries[0].avg_exec_time_ms == 150.5

    def test_csv_parsing(self, tmp_path):
        """Test CSV query parsing."""
        csv_file = tmp_path / "queries.csv"
        csv_file.write_text("query_id,query_text,query_type,avg_exec_time_ms\nq1,SELECT 1,SELECT,200.0\nq2,INSERT INTO t VALUES(1),INSERT,50.0\n")
        conn = OnPremDumpConnector(onprem_csv_path=str(csv_file))
        conn.validate_credentials()
        qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 2
        assert qh.queries[0].query_type == "SELECT"
        assert qh.queries[1].query_type == "INSERT"


class TestConnectorCredentialValidation:
    """Test credential validation for each connector."""

    def test_snowflake_requires_account_and_user(self):
        """Test Snowflake requires ACCOUNT and USER."""
        conn = SnowflakeConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_redshift_requires_cluster_and_user(self):
        """Test Redshift requires CLUSTER_ID and USER."""
        conn = RedshiftConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_bigquery_requires_project_id(self):
        """Test BigQuery requires PROJECT_ID."""
        conn = BigQueryConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_synapse_requires_server_and_user(self):
        """Test Synapse requires SERVER and USER."""
        conn = SynapseConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_postgres_requires_host_and_user(self):
        """Test PostgreSQL requires HOST and USER."""
        conn = PostgresConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_oracle_requires_host_and_user(self):
        """Test Oracle requires HOST and USER."""
        conn = OracleConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_vertica_requires_host_and_user(self):
        """Test Vertica requires HOST and USER."""
        conn = VerticaConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()

    def test_teradata_requires_host_and_user(self):
        """Test Teradata requires HOST and USER."""
        conn = TeradataConnector()
        with pytest.raises(ValueError):
            conn.validate_credentials()
