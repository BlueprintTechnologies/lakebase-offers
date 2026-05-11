"""Tests for AccessPatternSignals and related models."""

import pytest
from src.models.access_patterns import (
    AccessPatternSignals,
    CacheCandidate,
    QueryTemporalBucket,
)


class TestQueryTemporalBucket:
    def test_basic_construction(self):
        b = QueryTemporalBucket(
            hour_of_day=9,
            day_of_week=1,
            avg_query_count=150.0,
            avg_exec_time_ms=250.0,
        )
        assert b.hour_of_day == 9
        assert b.day_of_week == 1
        assert b.avg_query_count == 150.0


class TestCacheCandidate:
    def test_basic_construction(self):
        cc = CacheCandidate(
            query_fingerprint="abc123",
            execution_count=100,
            avg_exec_time_ms=500.0,
            avg_rows_returned=50.0,
            data_freshness_hours=24.0,
            estimated_cache_hit_rate=0.85,
            recommended_ttl_seconds=3600,
            cache_type="result_cache",
        )
        assert cc.query_fingerprint == "abc123"
        assert cc.estimated_cache_hit_rate == 0.85
        assert cc.cache_type == "result_cache"


class TestAccessPatternSignals:
    def test_defaults(self):
        ap = AccessPatternSignals(platform="snowflake")
        assert ap.platform == "snowflake"
        assert ap.read_write_ratio == 0.0
        assert ap.point_lookup_pct == 0.0
        assert ap.full_scan_pct == 0.0
        assert ap.cache_candidates == []
        assert ap.temporal_buckets == []
        assert ap.peak_hour_of_day == 0
        assert ap.has_burst_pattern is False

    def test_full_construction(self):
        buckets = [
            QueryTemporalBucket(hour_of_day=9, day_of_week=1, avg_query_count=100.0, avg_exec_time_ms=200.0),
            QueryTemporalBucket(hour_of_day=14, day_of_week=2, avg_query_count=300.0, avg_exec_time_ms=180.0),
        ]
        candidates = [
            CacheCandidate(
                query_fingerprint="fp1",
                execution_count=50,
                avg_exec_time_ms=500.0,
                avg_rows_returned=20.0,
                data_freshness_hours=1.0,
                estimated_cache_hit_rate=0.9,
                recommended_ttl_seconds=1800,
                cache_type="redis",
            )
        ]
        ap = AccessPatternSignals(
            platform="snowflake",
            read_write_ratio=0.85,
            point_lookup_pct=0.3,
            full_scan_pct=0.05,
            cache_candidates=candidates,
            estimated_cacheable_pct=0.25,
            temporal_buckets=buckets,
            peak_hour_of_day=14,
            peak_day_of_week=2,
            has_burst_pattern=True,
            burst_duration_minutes=30,
        )
        assert ap.read_write_ratio == 0.85
        assert ap.peak_hour_of_day == 14
        assert ap.has_burst_pattern is True
        assert len(ap.cache_candidates) == 1
