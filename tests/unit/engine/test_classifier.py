"""Tests for WorkloadClassifier."""

import pytest
from unittest.mock import MagicMock
from src.engine.classifier import (
    WorkloadClassifier,
    BUCKET_ANALYTICS,
    BUCKET_POINT_LOOKUPS,
    BUCKET_AGENT_STATE,
    BUCKET_APP_BACKENDS,
    BUCKET_FEATURE_SERVING,
    BUCKET_HEAVY_ETL,
    BUCKET_REALTIME,
)


def _make_score(identifier="test_wl", classification="Analytics", score=15.0,
                pain=3, business_impact=3, complexity=2):
    s = MagicMock()
    s.identifier = identifier
    s.classification = classification
    s.adjusted_score = score
    s.pain = pain
    s.business_impact = business_impact
    s.complexity = complexity
    return s


class TestClassifyAll:
    def test_returns_all_buckets(self):
        clf = WorkloadClassifier()
        result = clf.classify_all([])
        assert BUCKET_ANALYTICS in result
        assert BUCKET_POINT_LOOKUPS in result
        assert BUCKET_AGENT_STATE in result
        assert BUCKET_APP_BACKENDS in result
        assert BUCKET_HEAVY_ETL in result
        assert BUCKET_REALTIME in result

    def test_empty_input_all_buckets_empty(self):
        clf = WorkloadClassifier()
        result = clf.classify_all([])
        for bucket_items in result.values():
            assert bucket_items == []

    def test_high_complexity_high_pain_goes_to_heavy_etl(self):
        clf = WorkloadClassifier()
        score = _make_score(complexity=4, pain=3)
        result = clf.classify_all([score])
        assert len(result[BUCKET_HEAVY_ETL]) == 1
        assert result[BUCKET_HEAVY_ETL][0]["identifier"] == "test_wl"

    def test_high_business_impact_high_score_goes_to_realtime(self):
        clf = WorkloadClassifier()
        score = _make_score(business_impact=4, score=20.0, complexity=2, pain=2)
        result = clf.classify_all([score])
        assert len(result[BUCKET_REALTIME]) == 1

    def test_low_complexity_moderate_pain_goes_to_point_lookups(self):
        clf = WorkloadClassifier()
        score = _make_score(complexity=2, pain=3, business_impact=2, score=10.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_POINT_LOOKUPS]) == 1

    def test_agent_in_name_goes_to_agent_state(self):
        clf = WorkloadClassifier()
        score = _make_score("agent_state_tracker", complexity=3, pain=2,
                            business_impact=2, score=10.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_AGENT_STATE]) == 1

    def test_state_in_name_goes_to_agent_state(self):
        clf = WorkloadClassifier()
        score = _make_score("session_state_table", complexity=3, pain=2,
                            business_impact=2, score=10.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_AGENT_STATE]) == 1

    def test_app_in_name_goes_to_app_backends(self):
        clf = WorkloadClassifier()
        score = _make_score("app_user_lookup", complexity=3, pain=2,
                            business_impact=2, score=10.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_APP_BACKENDS]) == 1

    def test_api_in_name_goes_to_app_backends(self):
        clf = WorkloadClassifier()
        score = _make_score("api_gateway_queries", complexity=3, pain=2,
                            business_impact=2, score=10.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_APP_BACKENDS]) == 1

    def test_feature_in_name_goes_to_feature_serving(self):
        clf = WorkloadClassifier()
        score = _make_score("feature_store_lookup", complexity=3, pain=2,
                            business_impact=2, score=8.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_FEATURE_SERVING]) == 1

    def test_high_score_analytics_goes_to_app_backends(self):
        clf = WorkloadClassifier()
        score = _make_score("plain_analytics_wl", complexity=3, pain=2,
                            business_impact=2, score=30.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_APP_BACKENDS]) == 1

    def test_default_low_score_goes_to_analytics(self):
        clf = WorkloadClassifier()
        score = _make_score("plain_query", complexity=3, pain=2,
                            business_impact=2, score=5.0)
        result = clf.classify_all([score])
        assert len(result[BUCKET_ANALYTICS]) == 1

    def test_dict_input_supported(self):
        clf = WorkloadClassifier()
        # complexity=3, pain=1 avoids point_lookup rule (complexity<=2 and pain>=2)
        score_dict = {
            "identifier": "dict_wl",
            "classification": "Analytics",
            "adjusted_score": 5.0,
            "pain": 1,
            "business_impact": 1,
            "complexity": 3,
        }
        result = clf.classify_all([score_dict])
        assert len(result[BUCKET_ANALYTICS]) == 1
        assert result[BUCKET_ANALYTICS][0]["identifier"] == "dict_wl"

    def test_invalid_input_skipped(self):
        clf = WorkloadClassifier()
        result = clf.classify_all([42, "not_a_score", None])
        for bucket_items in result.values():
            assert bucket_items == []

    def test_multiple_scores_distributed(self):
        clf = WorkloadClassifier()
        scores = [
            _make_score("wl1", complexity=4, pain=3),
            _make_score("feature_wl", complexity=3, pain=2, business_impact=2, score=8.0),
            _make_score("simple_wl", complexity=1, pain=1, business_impact=1, score=3.0),
        ]
        result = clf.classify_all(scores)
        total = sum(len(v) for v in result.values())
        assert total == 3

    def test_bucket_items_contain_required_keys(self):
        clf = WorkloadClassifier()
        score = _make_score("wl", complexity=2, pain=2, business_impact=2, score=5.0)
        result = clf.classify_all([score])
        bucket_items = [item for items in result.values() for item in items]
        assert len(bucket_items) == 1
        item = bucket_items[0]
        assert "identifier" in item
        assert "adjusted_score" in item
        assert "pain" in item
        assert "business_impact" in item
        assert "complexity" in item


class TestClassifySingle:
    def test_score_object_classified(self):
        clf = WorkloadClassifier()
        score = _make_score("wl", complexity=2, pain=2, business_impact=2, score=5.0)
        result = clf.classify_single(score)
        assert isinstance(result, str)
        assert result in (BUCKET_ANALYTICS, BUCKET_POINT_LOOKUPS, BUCKET_AGENT_STATE,
                          BUCKET_APP_BACKENDS, BUCKET_FEATURE_SERVING, BUCKET_HEAVY_ETL,
                          BUCKET_REALTIME)

    def test_non_score_object_returns_analytics(self):
        clf = WorkloadClassifier()
        result = clf.classify_single("not_a_score")
        assert result == BUCKET_ANALYTICS
