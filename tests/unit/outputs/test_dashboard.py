"""Tests for dashboard module (generate_dashboard_html)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


def _make_score(identifier="wl1", score=20.0, priority="Priority_1"):
    s = MagicMock()
    s.identifier = identifier
    s.adjusted_score = score
    s.priority = priority
    s.classification = "Analytics"
    s.pain = 3
    s.business_impact = 4
    s.complexity = 2
    s.effort_tshirt_size = "M"
    s.recommendation = "Migrate to Lakebase"
    return s


class TestGenerateDashboardHtml:
    def test_creates_html_file(self, tmp_path):
        from src.outputs.dashboard import generate_dashboard_html
        out = str(tmp_path / "dash.html")
        result = generate_dashboard_html({}, {}, {}, out)
        assert result == out
        assert Path(out).exists()

    def test_empty_data_has_no_data_text(self, tmp_path):
        from src.outputs.dashboard import generate_dashboard_html
        out = str(tmp_path / "empty.html")
        generate_dashboard_html({}, {}, {}, out)
        content = Path(out).read_text()
        assert "No data" in content

    def test_with_scores_produces_content(self, tmp_path):
        from src.outputs.dashboard import generate_dashboard_html
        scores = {"snowflake": [_make_score("wl1", 25.0, "Priority_1")]}
        out = str(tmp_path / "dashboard.html")
        generate_dashboard_html(scores, {}, {}, out)
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0

    def test_returns_output_path(self, tmp_path):
        from src.outputs.dashboard import generate_dashboard_html
        out = str(tmp_path / "out.html")
        result = generate_dashboard_html({}, {}, {}, out)
        assert result == out
