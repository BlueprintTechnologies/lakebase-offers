"""Tests for AssessmentConfig and load_config."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.config import AssessmentConfig, load_config, default_config


class TestAssessmentConfigDefaults:
    def test_default_target_platforms(self):
        cfg = AssessmentConfig(target_platforms=["snowflake"])
        assert isinstance(cfg.target_platforms, list)
        assert "snowflake" in cfg.target_platforms

    def test_default_output_formats(self):
        cfg = AssessmentConfig(target_platforms=[])
        assert "pdf" in cfg.output_formats

    def test_default_query_history_days(self):
        cfg = AssessmentConfig(target_platforms=[])
        assert cfg.query_history_days == 90

    def test_default_min_opportunity_score(self):
        cfg = AssessmentConfig(target_platforms=[])
        # Access the class constant
        assert AssessmentConfig.DEFAULT_QUERY_HISTORY_DAYS == 90

    def test_empty_target_platforms(self):
        cfg = AssessmentConfig(target_platforms=[])
        assert cfg.target_platforms == []


class TestAssessmentConfigGetConnector:
    def test_get_snowflake_connector(self):
        cfg = AssessmentConfig(target_platforms=["snowflake"])
        cfg.raw_env = {"SNOWFLAKE_ACCOUNT": "acc", "SNOWFLAKE_USER": "user", "SNOWFLAKE_PASSWORD": "pw"}
        conn = cfg.get_connector("snowflake")
        from src.connectors.snowflake import SnowflakeConnector
        assert isinstance(conn, SnowflakeConnector)

    def test_get_bigquery_connector(self):
        cfg = AssessmentConfig(target_platforms=["bigquery"])
        cfg.raw_env = {"BQ_PROJECT_ID": "my-project"}
        conn = cfg.get_connector("bigquery")
        from src.connectors.bigquery import BigQueryConnector
        assert isinstance(conn, BigQueryConnector)

    def test_get_postgres_connector(self):
        cfg = AssessmentConfig(target_platforms=["postgres"])
        cfg.raw_env = {"PG_HOST": "localhost", "PG_USER": "user"}
        conn = cfg.get_connector("postgres")
        from src.connectors.postgres import PostgresConnector
        assert isinstance(conn, PostgresConnector)

    def test_get_redshift_connector(self):
        cfg = AssessmentConfig(target_platforms=["redshift"])
        cfg.raw_env = {"REDSHIFT_CLUSTER_ID": "cluster", "REDSHIFT_USER": "admin"}
        conn = cfg.get_connector("redshift")
        from src.connectors.redshift import RedshiftConnector
        assert isinstance(conn, RedshiftConnector)

    def test_get_mysql_connector(self):
        cfg = AssessmentConfig(target_platforms=["mysql"])
        cfg.raw_env = {"MYSQL_HOST": "localhost", "MYSQL_USER": "user"}
        conn = cfg.get_connector("mysql")
        from src.connectors.mysql import MySQLConnector
        assert isinstance(conn, MySQLConnector)

    def test_get_databricks_connector(self):
        cfg = AssessmentConfig(target_platforms=["databricks"])
        cfg.raw_env = {"DATABRICKS_HOST": "myhost", "DATABRICKS_TOKEN": "tok"}
        conn = cfg.get_connector("databricks")
        from src.connectors.databricks import DatabricksConnector
        assert isinstance(conn, DatabricksConnector)

    def test_get_oracle_connector(self):
        cfg = AssessmentConfig(target_platforms=["oracle"])
        cfg.raw_env = {"ORACLE_HOST": "myhost", "ORACLE_USER": "admin"}
        conn = cfg.get_connector("oracle")
        from src.connectors.oracle import OracleConnector
        assert isinstance(conn, OracleConnector)

    def test_get_synapse_connector(self):
        cfg = AssessmentConfig(target_platforms=["synapse"])
        cfg.raw_env = {"SYNAPSE_SERVER": "myserver", "SYNAPSE_USER": "admin"}
        conn = cfg.get_connector("synapse")
        from src.connectors.synapse import SynapseConnector
        assert isinstance(conn, SynapseConnector)

    def test_get_teradata_connector(self):
        cfg = AssessmentConfig(target_platforms=["teradata"])
        cfg.raw_env = {"TERADATA_HOST": "myhost", "TERADATA_USER": "admin"}
        conn = cfg.get_connector("teradata")
        from src.connectors.teradata import TeradataConnector
        assert isinstance(conn, TeradataConnector)

    def test_get_vertica_connector(self):
        cfg = AssessmentConfig(target_platforms=["vertica"])
        cfg.raw_env = {"VERTICA_HOST": "myhost", "VERTICA_USER": "admin"}
        conn = cfg.get_connector("vertica")
        from src.connectors.vertica import VerticaConnector
        assert isinstance(conn, VerticaConnector)

    def test_unknown_platform_raises(self):
        cfg = AssessmentConfig(target_platforms=[])
        with pytest.raises((ValueError, KeyError)):
            cfg.get_connector("unknown_platform_xyz")


class TestLoadConfig:
    def test_load_with_none_path_returns_default(self):
        cfg = load_config(None)
        assert isinstance(cfg, AssessmentConfig)

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_load_valid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "target_platforms": ["snowflake"],
            "query_history_days": 30,
        }))
        cfg = load_config(str(config_file))
        assert "snowflake" in cfg.target_platforms
        assert cfg.query_history_days == 30

    def test_load_yaml_without_platforms_raises(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("{}")
        with pytest.raises(ValueError, match="target_platforms"):
            load_config(str(config_file))

    def test_load_yaml_with_output_formats(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "target_platforms": ["mysql"],
            "output_formats": ["json", "csv"],
        }))
        cfg = load_config(str(config_file))
        assert "json" in cfg.output_formats


class TestDefaultConfig:
    def test_returns_assessment_config(self):
        cfg = default_config()
        assert isinstance(cfg, AssessmentConfig)

    def test_has_default_platforms(self):
        cfg = default_config()
        assert len(cfg.target_platforms) > 0
        assert "snowflake" in cfg.target_platforms
