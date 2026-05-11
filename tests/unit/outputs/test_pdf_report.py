"""Tests for PdfReportGenerator (mirrored from src/outputs/pdf_report.py)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.outputs.pdf_report import PdfReportGenerator


def _make_score(identifier="wl1", score=20.0, priority="Priority_1",
                classification="Analytics"):
    s = MagicMock()
    s.identifier = identifier
    s.adjusted_score = score
    s.priority = priority
    s.classification = classification
    s.pain = 3
    s.business_impact = 4
    s.complexity = 2
    s.effort_tshirt_size = "M"
    s.recommendation = "Migrate to Lakebase"
    return s


def _cost_delta(platform="snowflake"):
    return {
        "platform": "Snowflake",
        "platform_key": platform,
        "current_estimated_monthly_cost": 10000.0,
        "projected_lakebase_cost": 7000.0,
        "savings_pct": 30.0,
    }


class TestPdfReportGeneratorInit:
    def test_init_with_empty_data(self):
        gen = PdfReportGenerator({}, {}, {})
        assert gen.scores == {}
        assert gen.cost_deltas == {}
        assert gen.buckets == {}

    def test_init_with_data(self):
        scores = {"sf": [_make_score()]}
        gen = PdfReportGenerator(scores, {}, {})
        assert "sf" in gen.scores

    def test_misuse_findings_defaults_to_empty(self):
        gen = PdfReportGenerator({}, {}, {})
        assert gen.misuse_findings == {}

    def test_readiness_scores_defaults_to_empty(self):
        gen = PdfReportGenerator({}, {}, {})
        assert gen.readiness_scores == {}

    def test_anti_pattern_constants(self):
        assert len(PdfReportGenerator.ANTI_PATTERN_LABELS) == 6
        assert len(PdfReportGenerator.ANTI_PATTERN_TYPES) == 6


class TestGenerate:
    def test_creates_pdf(self, tmp_path):
        gen = PdfReportGenerator({"sf": [_make_score()]}, {"sf": _cost_delta()}, {})
        out = str(tmp_path / "report.pdf")
        result = gen.generate(out)
        assert result == out
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0

    def test_empty_data_pdf(self, tmp_path):
        gen = PdfReportGenerator({}, {}, {})
        out = str(tmp_path / "empty.pdf")
        result = gen.generate(out)
        assert Path(out).exists()

    def test_multiple_platforms(self, tmp_path):
        scores = {
            "snowflake": [_make_score("sf_wl", 25.0)],
            "bigquery": [_make_score("bq_wl", 12.0, "Evaluate")],
        }
        cost_deltas = {"snowflake": _cost_delta("snowflake"), "bigquery": _cost_delta("bigquery")}
        gen = PdfReportGenerator(scores, cost_deltas, {})
        out = str(tmp_path / "multi.pdf")
        gen.generate(out)
        assert Path(out).exists()

    def test_with_migration_buckets(self, tmp_path):
        buckets = {
            "Analytics → Keep in Delta": [{"identifier": "wl1", "adjusted_score": 5.0}],
            "Point Lookups → Migrate to Lakebase": [{"identifier": "wl2", "adjusted_score": 20.0}],
        }
        gen = PdfReportGenerator({"sf": [_make_score()]}, {"sf": _cost_delta()}, buckets)
        out = str(tmp_path / "buckets.pdf")
        gen.generate(out)
        assert Path(out).exists()

    def test_with_readiness_scores(self, tmp_path):
        rs = MagicMock()
        rs.total_score = 75
        rs.tier = "Conditionally Ready"
        rs.pillar_gaps = ["Cost & Business Case"]
        rs.recommended_next_step = "Run pilot"
        rs.data_readiness_score = 20
        rs.sql_compatibility_score = 18
        rs.access_governance_score = 16
        rs.cost_business_case_score = 10
        rs.org_readiness_score = 11
        gen = PdfReportGenerator(
            {"sf": [_make_score()]}, {"sf": _cost_delta()}, {},
            readiness_scores={"sf": rs},
        )
        out = str(tmp_path / "readiness.pdf")
        gen.generate(out)
        assert Path(out).exists()

    def test_with_misuse_findings(self, tmp_path):
        from src.models.databricks_misuse import (
            DatabricksMisuseFindings, MisuseFinding, FINDING_HIGH_FREQ_POINT_LOOKUP
        )
        finding = MisuseFinding(
            finding_type=FINDING_HIGH_FREQ_POINT_LOOKUP,
            severity="high",
            affected_object="orders_table",
            description="High frequency lookups",
            recommendation="Migrate",
        )
        misuse = DatabricksMisuseFindings(platform="snowflake", findings=[finding])
        gen = PdfReportGenerator(
            {"sf": [_make_score()]}, {"sf": _cost_delta()}, {},
            misuse_findings={"sf": misuse},
        )
        out = str(tmp_path / "misuse.pdf")
        gen.generate(out)
        assert Path(out).exists()

    def test_hold_priority_scores(self, tmp_path):
        scores = {"sf": [_make_score("hold_wl", 3.0, "Hold")]}
        gen = PdfReportGenerator(scores, {"sf": _cost_delta()}, {})
        out = str(tmp_path / "hold.pdf")
        gen.generate(out)
        assert Path(out).exists()


class TestGenerateDashboard:
    def test_no_data_produces_html(self, tmp_path):
        gen = PdfReportGenerator({}, {}, {})
        out = str(tmp_path / "dashboard.html")
        result = gen.generate_dashboard(out)
        assert result == out
        assert Path(out).exists()
        content = Path(out).read_text()
        assert "No data" in content

    def test_with_scores_produces_charts(self, tmp_path):
        scores = {
            "snowflake": [
                _make_score("wl1", 25.0, "Priority_1"),
                _make_score("wl2", 10.0, "Evaluate"),
                _make_score("wl3", 3.0, "Hold"),
            ]
        }
        gen = PdfReportGenerator(scores, {"snowflake": _cost_delta()}, {})
        out = str(tmp_path / "dashboard.html")
        gen.generate_dashboard(out)
        assert Path(out).exists()
        content = Path(out).read_text()
        assert len(content) > 1000

    def test_multiple_platforms_dashboard(self, tmp_path):
        scores = {
            "snowflake": [_make_score("sf_wl", 20.0)],
            "bigquery": [_make_score("bq_wl", 12.0)],
        }
        gen = PdfReportGenerator(scores, {}, {})
        out = str(tmp_path / "multi_dashboard.html")
        gen.generate_dashboard(out)
        assert Path(out).exists()
