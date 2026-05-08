"""Tests for JsonExporter."""

import csv
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.outputs.json_export import JsonExporter


def _make_score(identifier="wl1", score=15.0, priority="Priority_1"):
    s = MagicMock()
    s.identifier = identifier
    s.adjusted_score = score
    s.pain = 3
    s.business_impact = 3
    s.complexity = 2
    s.raw_score = score
    s.priority = priority
    s.classification = "Analytics"
    return s


class TestJsonExporterExport:
    def test_creates_json_file(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        exporter.export({"sf": [_make_score()]}, {"sf": {"savings_pct": 30}}, {}, out)
        assert Path(out).exists()

    def test_valid_json_output(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        exporter.export({"sf": [_make_score()]}, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert "generated_at" in data
        assert "version" in data
        assert "scores" in data

    def test_includes_checksum(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        exporter.export({}, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert "checksum" in data
        assert len(data["checksum"]) == 64

    def test_cost_deltas_included(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        cost_deltas = {"snowflake": {"savings_pct": 35.0, "current_estimated_monthly_cost": 10000.0}}
        exporter.export({}, cost_deltas, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert data["cost_deltas"]["snowflake"]["savings_pct"] == 35.0

    def test_migration_buckets_included(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        buckets = {"Analytics": [{"identifier": "wl1", "adjusted_score": 20.0}]}
        exporter.export({}, {}, buckets, out)
        with open(out) as f:
            data = json.load(f)
        assert "Analytics" in data["migration_buckets"]

    def test_scores_serialized_from_dataclass(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        score = _make_score()
        exporter.export({"snowflake": [score]}, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert len(data["scores"]["snowflake"]) == 1

    def test_scores_from_dict(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        score_dict = {"identifier": "wl1", "adjusted_score": 20.0, "priority": "Priority_1"}
        exporter.export({"snowflake": [score_dict]}, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert data["scores"]["snowflake"][0]["identifier"] == "wl1"

    def test_scores_from_unknown_type(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        exporter.export({"test": ["plain_string"]}, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert len(data["scores"]["test"]) == 1

    def test_returns_output_path(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        result = exporter.export({}, {}, {}, out)
        assert result == out

    def test_multiple_platforms(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.json")
        scores = {
            "snowflake": [_make_score("sf_wl")],
            "bigquery": [_make_score("bq_wl", priority="Evaluate")],
        }
        exporter.export(scores, {}, {}, out)
        with open(out) as f:
            data = json.load(f)
        assert "snowflake" in data["scores"]
        assert "bigquery" in data["scores"]


class TestJsonExporterExportCsv:
    def test_creates_csv_file(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        exporter.export_csv({"sf": [_make_score()]}, out)
        assert Path(out).exists()

    def test_csv_has_header(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        exporter.export_csv({}, out)
        with open(out) as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "platform" in header
        assert "identifier" in header
        assert "adjusted_score" in header
        assert "priority" in header

    def test_csv_has_data_rows(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        exporter.export_csv({"snowflake": [_make_score("wl1"), _make_score("wl2")]}, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2

    def test_csv_dict_scores(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        scores = [{"identifier": "wl1", "adjusted_score": 15.0, "priority": "Priority_1",
                   "pain": 3, "business_impact": 3, "complexity": 2, "raw_score": 15.0,
                   "classification": "Analytics"}]
        exporter.export_csv({"test": scores}, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["identifier"] == "wl1"

    def test_returns_output_path(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        result = exporter.export_csv({}, out)
        assert result == out

    def test_platform_included_in_rows(self, tmp_path):
        exporter = JsonExporter()
        out = str(tmp_path / "report.csv")
        exporter.export_csv({"bigquery": [_make_score()]}, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["platform"] == "bigquery"
