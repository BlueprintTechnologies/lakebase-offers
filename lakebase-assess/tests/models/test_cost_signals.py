"""Tests for CostSignals model."""

import pytest
from src.models.cost_signals import CostSignals


class TestCostSignals:
    def test_basic_creation(self):
        cs = CostSignals(platform="snowflake")
        assert cs.platform == "snowflake"

    def test_defaults(self):
        cs = CostSignals(platform="test")
        assert cs.compute_units_per_month == 0.0
        assert cs.compute_unit_name == "unknown"
        assert cs.compute_cost_per_unit == 0.0
        assert cs.estimated_compute_cost_monthly == 0.0
        assert cs.storage_gb_total == 0.0
        assert cs.storage_cost_per_gb == 0.0
        assert cs.estimated_storage_cost_monthly == 0.0
        assert cs.bytes_scanned_per_month == 0.0
        assert cs.io_cost_per_mb == 0.0
        assert cs.estimated_io_cost_monthly == 0.0
        assert cs.has_license_cost is False
        assert cs.license_type == "unknown"
        assert cs.estimated_license_cost_monthly == 0.0
        assert cs.total_estimated_monthly_cost == 0.0
        assert cs.cost_per_query == 0.0
        assert cs.cost_per_gb_scanned == 0.0
        assert cs.costs_from_billing_api is False

    def test_full_construction(self):
        cs = CostSignals(
            platform="snowflake",
            compute_units_per_month=300.0,
            compute_unit_name="credit",
            compute_cost_per_unit=3.0,
            estimated_compute_cost_monthly=900.0,
            storage_gb_total=1000.0,
            storage_cost_per_gb=0.023,
            estimated_storage_cost_monthly=23.0,
            bytes_scanned_per_month=1_000_000_000,
            io_cost_per_mb=0.000005,
            estimated_io_cost_monthly=4.77,
            has_license_cost=True,
            license_type="enterprise",
            estimated_license_cost_monthly=833.0,
            total_estimated_monthly_cost=1760.77,
            cost_per_query=0.003,
            cost_per_gb_scanned=0.001,
            costs_from_billing_api=True,
        )
        assert cs.compute_units_per_month == 300.0
        assert cs.compute_unit_name == "credit"
        assert cs.has_license_cost is True
        assert cs.license_type == "enterprise"
        assert cs.costs_from_billing_api is True

    def test_serialization(self):
        cs = CostSignals(platform="bigquery", total_estimated_monthly_cost=500.0)
        d = cs.model_dump()
        assert d["platform"] == "bigquery"
        assert d["total_estimated_monthly_cost"] == 500.0

    def test_platforms(self):
        for platform in ["snowflake", "redshift", "bigquery", "synapse",
                         "postgres", "oracle", "mysql", "databricks"]:
            cs = CostSignals(platform=platform)
            assert cs.platform == platform
