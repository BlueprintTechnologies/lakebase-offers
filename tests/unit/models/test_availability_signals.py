"""Tests for AvailabilitySignals model."""

import pytest
from src.models.availability_signals import AvailabilitySignals


class TestAvailabilitySignals:
    def test_defaults(self):
        av = AvailabilitySignals(platform="snowflake")
        assert av.platform == "snowflake"
        assert av.incidents_last_90d == 0
        assert av.avg_incident_duration_minutes == 0.0
        assert av.sla_target_pct == 99.9
        assert av.sla_actual_pct == 0.0
        assert av.planned_maintenance_windows == 0
        assert av.has_dr_configured is False
        assert av.rto_minutes is None
        assert av.rpo_minutes is None

    def test_full_construction(self):
        av = AvailabilitySignals(
            platform="redshift",
            incidents_last_90d=3,
            avg_incident_duration_minutes=25.0,
            sla_target_pct=99.95,
            sla_actual_pct=99.91,
            planned_maintenance_windows=2,
            has_dr_configured=True,
            rto_minutes=60,
            rpo_minutes=15,
        )
        assert av.incidents_last_90d == 3
        assert av.sla_target_pct == 99.95
        assert av.has_dr_configured is True
        assert av.rto_minutes == 60
        assert av.rpo_minutes == 15

    def test_sla_below_target(self):
        av = AvailabilitySignals(
            platform="postgres",
            sla_target_pct=99.99,
            sla_actual_pct=99.8,
        )
        assert av.sla_actual_pct < av.sla_target_pct
