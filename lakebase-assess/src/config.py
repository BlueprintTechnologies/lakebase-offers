"""YAML config loader, env var validation, and CLI arg parsing."""

import os
import sys
from pathlib import Path
from typing import Any

import yaml

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


PLATFORM_CONNECTOR_MAP = {
    "snowflake": SnowflakeConnector,
    "redshift": RedshiftConnector,
    "bigquery": BigQueryConnector,
    "synapse": SynapseConnector,
    "postgres": PostgresConnector,
    "oracle": OracleConnector,
    "vertica": VerticaConnector,
    "teradata": TeradataConnector,
    "onprem_dump": OnPremDumpConnector,
}


class AssessmentConfig:
    """Central configuration for the assessment pipeline."""

    DEFAULT_PRICING_MAP = Path(__file__).parent.parent / "pricing_maps" / "platform_rates.yaml"
    DEFAULT_DBU_MAP = Path(__file__).parent.parent / "pricing_maps" / "dbu_mapping.yaml"
    DEFAULT_QUERY_HISTORY_DAYS = 90
    DEFAULT_OUTPUT_FORMATS = ["pdf", "html", "json", "csv"]

    def __init__(
        self,
        target_platforms: list[str],
        query_history_days: int = DEFAULT_QUERY_HISTORY_DAYS,
        pricing_map_path: str | None = None,
        dbu_mapping_path: str | None = None,
        output_formats: list[str] | None = None,
        raw_env: dict[str, str] | None = None,
    ) -> None:
        self.target_platforms = target_platforms
        self.query_history_days = query_history_days
        self.pricing_map_path = pricing_map_path or str(self.DEFAULT_PRICING_MAP)
        self.dbu_mapping_path = dbu_mapping_path or str(self.DEFAULT_DBU_MAP)
        self.output_formats = output_formats or self.DEFAULT_OUTPUT_FORMATS
        self.raw_env = raw_env or dict(os.environ)
        self._pricing_map: dict[str, Any] | None = None

    # -- pricing -- #

    @property
    def pricing_map(self) -> dict[str, Any]:
        if self._pricing_map is None:
            p = Path(self.pricing_map_path)
            if not p.exists():
                raise FileNotFoundError(f"Pricing map not found: {self.pricing_map_path}")
            with open(p) as fh:
                self._pricing_map = yaml.safe_load(fh)
        return self._pricing_map

    # -- connector factory -- #

    def get_connector(self, platform: str) -> AbstractBaseConnector:
        cls = PLATFORM_CONNECTOR_MAP.get(platform)
        if cls is None:
            raise ValueError(f"Unknown platform: {platform}. Must be one of {list(PLATFORM_CONNECTOR_MAP.keys())}")
        env = self.raw_env
        kw: dict[str, Any] = {
            "query_history_days": self.query_history_days,
            "snowflake_account": env.get("SNOWFLAKE_ACCOUNT"),
            "snowflake_user": env.get("SNOWFLAKE_USER"),
            "snowflake_password": env.get("SNOWFLAKE_PASSWORD"),
            "snowflake_role": env.get("SNOWFLAKE_ROLE"),
            "snowflake_warehouse": env.get("SNOWFLAKE_WAREHOUSE"),
            "snowflake_database": env.get("SNOWFLAKE_DATABASE"),
            "snowflake_schema": env.get("SNOWFLAKE_SCHEMA"),
            "redshift_cluster_id": env.get("REDSHIFT_CLUSTER_ID"),
            "redshift_user": env.get("REDSHIFT_USER"),
            "redshift_password": env.get("REDSHIFT_PASSWORD"),
            "redshift_database": env.get("REDSHIFT_DATABASE"),
            "redshift_region": env.get("REDSHIFT_REGION", "us-east-1"),
            "bq_project_id": env.get("BQ_PROJECT_ID"),
            "bq_dataset": env.get("BQ_DATASET"),
            "bq_location": env.get("BQ_LOCATION"),
            "bq_credentials_path": env.get("BQ_CREDENTIALS_PATH"),
            "synapse_server": env.get("SYNAPSE_SERVER"),
            "synapse_database": env.get("SYNAPSE_DATABASE"),
            "synapse_user": env.get("SYNAPSE_USER"),
            "synapse_password": env.get("SYNAPSE_PASSWORD"),
            "synapse_tenant": env.get("SYNAPSE_TENANT"),
            "synapse_client_id": env.get("SYNAPSE_CLIENT_ID"),
            "synapse_client_secret": env.get("SYNAPSE_CLIENT_SECRET"),
            "pg_host": env.get("PG_HOST"),
            "pg_port": int(env.get("PG_PORT", "5432")),
            "pg_user": env.get("PG_USER"),
            "pg_password": env.get("PG_PASSWORD"),
            "pg_database": env.get("PG_DATABASE"),
            "oracle_host": env.get("ORACLE_HOST"),
            "oracle_port": int(env.get("ORACLE_PORT", "1521")),
            "oracle_service": env.get("ORACLE_SERVICE"),
            "oracle_user": env.get("ORACLE_USER"),
            "oracle_password": env.get("ORACLE_PASSWORD"),
            "vertica_host": env.get("VERTICA_HOST"),
            "vertica_port": int(env.get("VERTICA_PORT", "5433")),
            "vertica_user": env.get("VERTICA_USER"),
            "vertica_password": env.get("VERTICA_PASSWORD"),
            "vertica_database": env.get("VERTICA_DATABASE"),
            "teradata_host": env.get("TERADATA_HOST"),
            "teradata_port": int(env.get("TERADATA_PORT", "1025")),
            "teradata_user": env.get("TERADATA_USER"),
            "teradata_password": env.get("TERADATA_PASSWORD"),
        }
        # Remove None so the connector can distinguish between not-set vs explicit empty
        kw = {k: v for k, v in kw.items() if v is not None}
        return cls(platform_name=platform, **kw)

    def validate_connectors(self) -> None:
        """Attempt to connect to every configured platform; raises on first failure."""
        for platform in self.target_platforms:
            connector = self.get_connector(platform)
            connector.validate_credentials()


def load_config(config_path: str | None = None) -> AssessmentConfig:
    """Load config from YAML file or environment variables."""
    if config_path is None:
        return AssessmentConfig(target_platforms=[])

    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(p) as fh:
        data = yaml.safe_load(fh) or {}

    target_platforms = data.get("target_platforms", [])
    if not target_platforms:
        raise ValueError("Config must specify 'target_platforms'.")

    return AssessmentConfig(
        target_platforms=target_platforms,
        query_history_days=data.get("query_history_days", AssessmentConfig.DEFAULT_QUERY_HISTORY_DAYS),
        pricing_map_path=data.get("pricing_map_path"),
        dbu_mapping_path=data.get("dbu_mapping_path"),
        output_formats=data.get("output_formats"),
        raw_env=data.get("env_overrides", {}),
    )


# Default config for quick testing
def default_config() -> AssessmentConfig:
    return AssessmentConfig(target_platforms=["snowflake", "redshift", "bigquery"])
