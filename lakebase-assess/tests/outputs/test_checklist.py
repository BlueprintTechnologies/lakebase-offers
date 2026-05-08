"""Tests for ChecklistGenerator."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.outputs.checklist import ChecklistGenerator


def _make_score(identifier="wl1", priority="Priority_1", classification="Analytics", score=20.0):
    s = MagicMock()
    s.identifier = identifier
    s.priority = priority
    s.classification = classification
    s.adjusted_score = score
    return s


class TestChecklistGenerator:
    def test_creates_markdown_file(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        gen.generate({}, {}, out)
        assert Path(out).exists()

    def test_returns_output_path(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        result = gen.generate({}, {}, out)
        assert result == out

    def test_markdown_has_header(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        gen.generate({}, {}, out)
        content = Path(out).read_text()
        assert "# Lakebase Migration" in content

    def test_priority_1_section_present_when_applicable(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        scores = {"snowflake": [_make_score("wl1", "Priority_1")]}
        gen.generate(scores, {}, out)
        content = Path(out).read_text()
        assert "Priority 1" in content
        assert "wl1" in content

    def test_no_priority_section_when_no_priority_1(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        scores = {"snowflake": [_make_score("wl1", "Hold")]}
        gen.generate(scores, {}, out)
        content = Path(out).read_text()
        assert "Priority 1: High-Confidence" not in content

    def test_migration_buckets_section(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        buckets = {"Analytics → Keep in Delta": [{"identifier": "wl_a", "adjusted_score": 5.0}]}
        gen.generate({}, buckets, out)
        content = Path(out).read_text()
        assert "Migration Buckets" in content
        assert "wl_a" in content

    def test_pre_migration_checklist_always_present(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        gen.generate({}, {}, out)
        content = Path(out).read_text()
        assert "Pre-Migration Checklist" in content
        assert "- [ ]" in content

    def test_post_migration_validation_always_present(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        gen.generate({}, {}, out)
        content = Path(out).read_text()
        assert "Post-Migration Validation" in content

    def test_udf_platform_note_when_heavy_etl(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        scores = {"snowflake": [_make_score("wl1", "Priority_1", "Heavy ETL/UDF")]}
        gen.generate(scores, {}, out)
        content = Path(out).read_text()
        assert "UDF" in content or "refactoring" in content.lower()

    def test_empty_buckets_not_rendered(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        buckets = {"Empty Bucket": [], "Full Bucket": [{"identifier": "wl1", "adjusted_score": 5.0}]}
        gen.generate({}, buckets, out)
        content = Path(out).read_text()
        assert "Empty Bucket" not in content
        assert "Full Bucket" in content

    def test_dict_score_priority_1(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        scores = {"test": [{"identifier": "dict_wl", "priority": "Priority_1", "adjusted_score": 25.0}]}
        gen.generate(scores, {}, out)
        content = Path(out).read_text()
        assert "dict_wl" in content

    def test_multiple_platforms(self, tmp_path):
        gen = ChecklistGenerator()
        out = str(tmp_path / "checklist.md")
        scores = {
            "snowflake": [_make_score("sf_wl", "Priority_1")],
            "bigquery": [_make_score("bq_wl", "Evaluate")],
        }
        gen.generate(scores, {}, out)
        content = Path(out).read_text()
        assert "sf_wl" in content
