"""Tests for BillingCalculator."""

import pytest
from unittest.mock import MagicMock
from src.engine.billing import BillingCalculator, DEFAULT_RATES, LAKEBASE_RATES
from src.models.cost_signals import CostSignals


class TestBillingCalculatorInit:
    def test_default_rates_loaded(self):
        calc = BillingCalculator()
        assert "snowflake" in calc._rates
        assert "redshift" in calc._rates
        assert "bigquery" in calc._rates

    def test_pricing_map_nonexistent_path(self):
        calc = BillingCalculator(pricing_map_path="/nonexistent/rates.yaml")
        assert "snowflake" in calc._rates

    def test_pricing_map_overrides_defaults(self, tmp_path):
        yaml_file = tmp_path / "rates.yaml"
        yaml_file.write_text("platform_rates:\n  snowflake:\n    base_compute: 99.0\n")
        calc = BillingCalculator(pricing_map_path=str(yaml_file))
        assert calc._rates["snowflake"]["base_compute"] == 99.0

    def test_get_rates_for_platform(self):
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("snowflake")
        assert "base_compute" in rates
        assert "storage" in rates

    def test_get_rates_for_unknown_platform_returns_default(self):
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("unknown_platform")
        assert isinstance(rates, dict)

    def test_get_rates_normalizes_platform_name(self):
        calc = BillingCalculator()
        rates = calc.get_rates_for_platform("Snowflake")
        assert rates == calc.get_rates_for_platform("snowflake")


class TestCalculateCostDeltaWithSignals:
    def _cost_signals(self, **overrides):
        defaults = dict(
            platform="snowflake",
            total_estimated_monthly_cost=10000.0,
            estimated_compute_cost_monthly=8000.0,
            estimated_storage_cost_monthly=1500.0,
            estimated_io_cost_monthly=500.0,
            storage_gb_total=100.0,
            bytes_scanned_per_month=1_000_000_000,
            compute_units_per_month=300.0,
            compute_unit_name="credit",
            has_license_cost=False,
            estimated_license_cost_monthly=0.0,
        )
        defaults.update(overrides)
        return CostSignals(**defaults)

    def test_returns_dict_with_required_keys(self):
        calc = BillingCalculator()
        cs = self._cost_signals()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert "current_estimated_monthly_cost" in result
        assert "projected_lakebase_cost" in result
        assert "savings_pct" in result
        assert "platform" in result
        assert "platform_key" in result

    def test_current_cost_matches_signals(self):
        calc = BillingCalculator()
        cs = self._cost_signals(total_estimated_monthly_cost=12345.0)
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["current_estimated_monthly_cost"] == 12345.0

    def test_projected_cost_is_less_than_current(self):
        calc = BillingCalculator()
        cs = self._cost_signals()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["projected_lakebase_cost"] < result["current_estimated_monthly_cost"]

    def test_savings_pct_positive(self):
        calc = BillingCalculator()
        cs = self._cost_signals()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["savings_pct"] > 0

    def test_savings_pct_zero_when_no_cost(self):
        calc = BillingCalculator()
        cs = self._cost_signals(total_estimated_monthly_cost=0.0, estimated_compute_cost_monthly=0.0)
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["savings_pct"] == 0.0

    def test_license_savings_subtracted(self):
        calc = BillingCalculator()
        cs_no_license = self._cost_signals(has_license_cost=False, estimated_license_cost_monthly=0.0)
        cs_with_license = self._cost_signals(has_license_cost=True, estimated_license_cost_monthly=500.0)
        r1 = calc.calculate_cost_delta("teradata", "Teradata", cs_no_license)
        r2 = calc.calculate_cost_delta("teradata", "Teradata", cs_with_license)
        assert r2["projected_lakebase_cost"] <= r1["projected_lakebase_cost"]

    def test_projected_cost_never_negative(self):
        calc = BillingCalculator()
        cs = self._cost_signals(
            total_estimated_monthly_cost=1.0,
            estimated_compute_cost_monthly=1.0,
            storage_gb_total=0.0,
            bytes_scanned_per_month=0.0,
            has_license_cost=True,
            estimated_license_cost_monthly=1000.0,
        )
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["projected_lakebase_cost"] >= 0.0

    def test_data_source_set_to_actual_signals(self):
        calc = BillingCalculator()
        cs = self._cost_signals()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert result["cost_data_source"] == "actual_signals"

    def test_efficiency_gain_included(self):
        calc = BillingCalculator()
        cs = self._cost_signals()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", cs)
        assert "efficiency_gain" in result
        assert result["efficiency_gain"]["efficiency_gain_pct"] == LAKEBASE_RATES["efficiency_gain_pct"] * 100


class TestCalculateCostDeltaProxyFallback:
    def _make_score(self, raw_score=10.0):
        s = MagicMock()
        s.raw_score = raw_score
        s.identifier = "test_wl"
        return s

    def test_proxy_data_source(self):
        calc = BillingCalculator()
        scores = [self._make_score(10.0), self._make_score(20.0)]
        result = calc.calculate_cost_delta("snowflake", "Snowflake", None, scores)
        assert result["cost_data_source"] == "proxy_estimates"

    def test_proxy_no_scores(self):
        calc = BillingCalculator()
        result = calc.calculate_cost_delta("snowflake", "Snowflake", None, [])
        assert result["current_estimated_monthly_cost"] >= 0
        assert result["projected_lakebase_cost"] >= 0

    def test_proxy_with_scores(self):
        calc = BillingCalculator()
        scores = [self._make_score(s) for s in [5.0, 15.0, 25.0]]
        result = calc.calculate_cost_delta("bigquery", "BigQuery", None, scores)
        assert "current_estimated_monthly_cost" in result


class TestDefaultRates:
    def test_all_expected_platforms(self):
        platforms = {"snowflake", "redshift", "bigquery", "synapse", "oracle",
                     "vertica", "teradata", "databricks_sql"}
        assert platforms.issubset(set(DEFAULT_RATES.keys()))

    def test_each_platform_has_required_keys(self):
        for platform, rates in DEFAULT_RATES.items():
            assert "base_compute" in rates, f"{platform} missing base_compute"
            assert "storage" in rates, f"{platform} missing storage"

    def test_lakebase_rates_structure(self):
        assert "compute_dbu" in LAKEBASE_RATES
        assert "storage" in LAKEBASE_RATES
        assert "efficiency_gain_pct" in LAKEBASE_RATES
        assert 0 < LAKEBASE_RATES["efficiency_gain_pct"] < 1
