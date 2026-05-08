"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from src.cli import cli


class TestCliGroup:
    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "lakebase-assess" in result.output

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output
        assert "--platform" in result.output
        assert "--output-dir" in result.output

    def test_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_upload_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["upload", "--help"])
        assert result.exit_code == 0


class TestValidateCommand:
    def test_validate_with_no_config_fails_gracefully(self):
        from unittest.mock import patch, MagicMock
        runner = CliRunner()
        mock_cfg = MagicMock()
        mock_cfg.validate_connectors.side_effect = ValueError("No platforms configured")
        with patch("src.cli.load_config", return_value=mock_cfg):
            result = runner.invoke(cli, ["validate"])
        assert "Validation failed" in result.output or result.exit_code != 0

    def test_validate_succeeds_with_valid_config(self):
        from unittest.mock import patch, MagicMock
        runner = CliRunner()
        mock_cfg = MagicMock()
        mock_cfg.validate_connectors.return_value = None
        with patch("src.cli.load_config", return_value=mock_cfg):
            result = runner.invoke(cli, ["validate"])
        assert "validated" in result.output.lower() or result.exit_code == 0


class TestRunCommandDryRun:
    def test_dry_run_exits_without_queries(self):
        from unittest.mock import patch, MagicMock
        runner = CliRunner()
        mock_cfg = MagicMock()
        mock_cfg.target_platforms = ["snowflake"]
        mock_cfg.validate_connectors.return_value = None
        with patch("src.cli.load_config", return_value=mock_cfg):
            result = runner.invoke(cli, ["run", "--dry-run"])
        assert "Dry-run" in result.output or result.exit_code == 0
