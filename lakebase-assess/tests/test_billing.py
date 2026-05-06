"""Tests for the billing calculator."""

import pytest
import tempfile
import yaml

from src.engine.billing import BillingCalculator, DEFAULT_RATES, LAKEBASE_RATES


def _make_score(identifier="q1", raw_score=50.0, adjusted_score=50.0, priority="Hold"):
    """Helper to create a mock score."""
    from dataclasses import dataclass

    @dataclass
    class MockScore:
        identifier: str
        raw_score: float
        adjusted_score: float
        priority: str
        pain: int = 3
        business_impact: int = 3
        complexity: int = 3
        classification: str = "Analytics"

    return MockScore(identifier, raw_score, adjusted_score, priority)


class TestBillingCalculator:
    """Test the BillingCalculator."""

    def test_default_rates_exist(self):
        """Test that all expected platforms have default rates."""
        expected_platforms = ["snowflake", "redshift", "bigquery", "synapse",
                             "oracle", "vertica", "teradata", "databricks_sql"]
        for platform in expected_platforms:
            assert platform in DEFAULT_RATES

    def test_snowflake_rates(self):
        """Test Snowflake default rates match spec."""
        rates = DEFAULT_RATES["snowflake"]
        assert rates["base_compute"] == 28.0
        assert rates["storage"] == 0.023
        assert rates["io"] == 0.000005
        assert rates["scaling"] == 0.3

    def test_bigquery_compute_free(self):
        """Test BigQuery has zero compute cost."""
        rates = DEFAULT_RATES["bigquery"]
        assert rates["base_compute"] == 0.0
        assert rates["compute_unit"] == "compute_free"

    def test_databricks_sql_dbu_rates(self):
        """Test Databricks SQL DBU rates."""
        rates = DEFAULT_RATES["databricks_sql"]
        assert rates["base_compute"] == 0.072
        assert rates["storage"] == 0.04
        assert rates["io"] == 0.0

    def test_calculate_cost_delta_snowflake(self):
        """Test cost delta calculation for Snowflake."""
        calc = BillingCalculator()
        scores = [_make_score(raw_score=50.0) for _ in range(5)]
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", scores)

        assert "current_estimated_monthly_cost" in delta
        assert "projected_lakebase_cost" in delta
        assert "savings_pct" in delta
        assert "efficiency_gain" in delta
        assert delta["current_estimated_monthly_cost"] > 0
        assert delta["projected_lakebase_cost"] > 0

    def test_cost_delta_has_savings(self):
        """Test that savings_pct is computed."""
        calc = BillingCalculator()
        scores = [_make_score(raw_score=100.0) for _ in range(10)]
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", scores)
        assert "savings_pct" in delta

    def test_cost_delta_zero_scores(self):
        """Test cost delta with zero/empty scores (baseline costs)."""
        calc = BillingCalculator()
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", [])
        assert delta["current_estimated_monthly_cost"] > 0  # Baseline kicks in
        assert delta["projected_lakebase_cost"] > 0

    def test_cost_delta_oracle_ha_scaling(self):
        """Test Oracle with HA/DR scaling."""
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("Oracle")
        assert rates["scaling"] == 0.4
        assert rates["scaling_condition"] == "HA/DR"

    def test_cost_delta_vertica_ha_scaling(self):
        """Test Vertica with HA/DR scaling."""
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("Vertica")
        assert rates["scaling"] == 0.4

    def test_cost_delta_teradata_ha_scaling(self):
        """Test Teradata with HA/DR scaling."""
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("Teradata")
        assert rates["scaling"] == 0.4

    def test_custom_pricing_map(self):
        """Test loading custom pricing map from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "platform_rates": {
                    "snowflake": {
                        "base_compute": 35.0,
                        "compute_unit": "credit",
                        "storage": 0.025,
                        "storage_unit": "GB/mo",
                        "io": 0.000006,
                        "io_unit": "MB",
                        "scaling": 0.35,
                        "scaling_condition": "concurrency > 50",
                    },
                },
            }, f)
            f.flush()
            calc = BillingCalculator(pricing_map_path=f.name)

        rates = calc.get_rates_for_platform("snowflake")
        assert rates["base_compute"] == 35.0
        assert rates["storage"] == 0.025
        assert rates["io"] == 0.000006

    def test_lakebase_projected_rates(self):
        """Test Lakebase projected rates."""
        assert LAKEBASE_RATES["compute_dbu"] == 0.06
        assert LAKEBASE_RATES["storage"] == 0.04
        assert LAKEBASE_RATES["query_cost"] == 0.005
        assert LAKEBASE_RATES["efficiency_gain_pct"] == 0.3

    def test_efficiency_gain_metrics(self):
        """Test efficiency gain sub-metrics."""
        calc = BillingCalculator()
        scores = [_make_score(raw_score=100.0) for _ in range(10)]
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", scores)
        eff = delta["efficiency_gain"]
        assert "compute_hours_saved" in eff
        assert "cost_per_query_current" in eff
        assert "cost_per_query_lakebase" in eff
        assert "efficiency_gain_pct" in eff
        assert eff["efficiency_gain_pct"] == 30.0

    def test_cost_delta_bigquery_zero_compute(self):
        """Test BigQuery cost delta (compute is free)."""
        calc = BillingCalculator()
        scores = [_make_score(raw_score=50.0) for _ in range(5)]
        delta = calc.calculate_cost_delta("bigquery", "BigQuery", scores)
        # BigQuery has zero base compute, so current cost should be lower
        assert delta["current_estimated_monthly_cost"] > 0

    def test_cost_delta_synapse_dwu_rates(self):
        """Test Synapse DWU-hr rates."""
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("synapse")
        assert rates["base_compute"] == 0.42
        assert rates["compute_unit"] == "DWU-hr"


class TestBillingWithCostSignals:
    """Test BillingCalculator with actual CostSignals (item 4)."""

    def test_cost_delta_with_real_cost_signals(self):
        """Test cost delta calculation with CostSignals produces real values."""
        from src.models.cost_signals import CostSignals

        signals = CostSignals(
            platform="snowflake",
            compute_units_per_month=100.0,
            compute_unit_name="credit",
            compute_cost_per_unit=28.0,
            estimated_compute_cost_monthly=2800.0,
            storage_gb_total=500.0,
            storage_cost_per_gb=0.023,
            estimated_storage_cost_monthly=11.5,
            bytes_scanned_per_month=1000.0 * 1024 * 1024,
            io_cost_per_mb=0.000005,
            estimated_io_cost_monthly=0.005,
            total_estimated_monthly_cost=2811.505,
            costs_from_billing_api=True,
        )
        calc = BillingCalculator()
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", cost_signals=signals)

        assert delta["current_estimated_monthly_cost"] == 2811.51
        assert delta["cost_data_source"] == "actual_signals"
        assert delta["projected_lakebase_cost"] > 0
        assert "savings_pct" in delta

    def test_cost_delta_falls_back_to_proxy_when_no_signals(self):
        """Test that billing falls back to proxy estimates when no CostSignals."""
        calc = BillingCalculator()
        scores = [_make_score(raw_score=50.0) for _ in range(5)]
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", cost_signals=None, scores=scores)

        assert delta["cost_data_source"] == "proxy_estimates"
        assert delta["current_estimated_monthly_cost"] > 0

    def test_cost_delta_with_license_savings(self):
        """Test that Oracle license costs are factored into savings."""
        from src.models.cost_signals import CostSignals

        signals = CostSignals(
            platform="oracle",
            compute_units_per_month=2920.0,
            compute_unit_name="core-hr (amortized)",
            compute_cost_per_unit=2.0,
            estimated_compute_cost_monthly=5840.0,
            storage_gb_total=100.0,
            storage_cost_per_gb=0.035,
            estimated_storage_cost_monthly=3.5,
            has_license_cost=True,
            estimated_license_cost_monthly=833.33,
            total_estimated_monthly_cost=6676.83,
            costs_from_billing_api=False,
        )
        calc = BillingCalculator()
        delta = calc.calculate_cost_delta("oracle", "Oracle", cost_signals=signals)

        # Lakebase should save the license cost
        assert delta["projected_lakebase_cost"] < delta["current_estimated_monthly_cost"]
        assert delta["savings_pct"] > 0
