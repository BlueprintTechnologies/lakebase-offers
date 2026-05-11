"""Tests for ConcurrencySignals and ConcurrencySnapshot models."""

import pytest
from src.models.concurrency import ConcurrencySignals, ConcurrencySnapshot


class TestConcurrencySnapshot:
    def test_basic_construction(self):
        snap = ConcurrencySnapshot(
            timestamp="2026-05-01T10:00:00",
            active_sessions=5,
            queued_queries=2,
        )
        assert snap.timestamp == "2026-05-01T10:00:00"
        assert snap.active_sessions == 5
        assert snap.queued_queries == 2
        assert snap.avg_wait_time_ms is None
        assert snap.resource_utilization_cpu is None
        assert snap.resource_utilization_memory is None

    def test_full_construction(self):
        snap = ConcurrencySnapshot(
            timestamp="2026-05-01T10:00:00",
            active_sessions=10,
            queued_queries=3,
            avg_wait_time_ms=150.0,
            resource_utilization_cpu=0.75,
            resource_utilization_memory=0.60,
        )
        assert snap.avg_wait_time_ms == 150.0
        assert snap.resource_utilization_cpu == 0.75


class TestConcurrencySignals:
    def test_defaults(self):
        cs = ConcurrencySignals(platform="snowflake")
        assert cs.platform == "snowflake"
        assert cs.avg_concurrent_queries == 0.0
        assert cs.peak_concurrent_queries == 0
        assert cs.scaling_pressure == "low"
        assert cs.snapshots == []
        assert cs.timeout_rate == 0.0
        assert cs.slow_query_rate == 0.0

    def test_needs_scaling_high(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="high")
        assert cs.needs_scaling is True

    def test_needs_scaling_critical(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="critical")
        assert cs.needs_scaling is True

    def test_needs_scaling_medium(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="medium")
        assert cs.needs_scaling is False

    def test_needs_scaling_low(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="low")
        assert cs.needs_scaling is False

    def test_full_construction(self):
        snaps = [
            ConcurrencySnapshot(timestamp="ts1", active_sessions=5, queued_queries=1),
            ConcurrencySnapshot(timestamp="ts2", active_sessions=15, queued_queries=3),
        ]
        cs = ConcurrencySignals(
            platform="snowflake",
            snapshots=snaps,
            avg_concurrent_queries=10.0,
            peak_concurrent_queries=15,
            scaling_pressure="medium",
            timeout_rate=0.01,
            slow_query_rate=0.05,
        )
        assert len(cs.snapshots) == 2
        assert cs.avg_concurrent_queries == 10.0
        assert cs.peak_concurrent_queries == 15
