from datetime import datetime, timedelta, timezone

import pytest

from app.services.ranking.base_strategy import RankingStrategy
from app.services.ranking.default_strategy import DefaultRankingStrategy
from app.services.ranking.types import RankingCandidate


def _candidate(similarity_score=0.0, age_days=0):
    created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return RankingCandidate(
        resource_type="memory",
        resource_id=1,
        similarity_score=similarity_score,
        created_at=created_at,
    )


def test_implements_ranking_strategy_interface():
    assert isinstance(DefaultRankingStrategy(), RankingStrategy)


def test_zero_distance_gives_maximum_similarity_component():
    strategy = DefaultRankingStrategy(similarity_weight=1.0, recency_weight=0.0)

    assert strategy.score(_candidate(similarity_score=0.0, age_days=0)) == pytest.approx(1.0)


def test_larger_distance_scores_lower_all_else_equal():
    strategy = DefaultRankingStrategy(similarity_weight=1.0, recency_weight=0.0)
    close = _candidate(similarity_score=0.1, age_days=10)
    far = _candidate(similarity_score=5.0, age_days=10)

    assert strategy.score(close) > strategy.score(far)


def test_more_recent_candidate_scores_higher_all_else_equal():
    strategy = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0)
    recent = _candidate(similarity_score=1.0, age_days=1)
    old = _candidate(similarity_score=1.0, age_days=100)

    assert strategy.score(recent) > strategy.score(old)


def test_recency_component_is_half_at_exactly_one_half_life():
    strategy = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0, recency_half_life_days=30.0)

    assert strategy.score(_candidate(age_days=30)) == pytest.approx(0.5, abs=1e-3)


def test_recency_component_is_quarter_at_two_half_lives():
    strategy = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0, recency_half_life_days=30.0)

    assert strategy.score(_candidate(age_days=60)) == pytest.approx(0.25, abs=1e-3)


def test_recency_component_approaches_zero_for_very_old_candidates():
    strategy = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0, recency_half_life_days=30.0)

    assert strategy.score(_candidate(age_days=3000)) < 0.001


def test_future_created_at_is_treated_as_maximally_recent():
    strategy = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0)

    assert strategy.score(_candidate(age_days=-5)) == pytest.approx(1.0)


def test_weights_are_configurable_and_isolate_each_component():
    candidate = _candidate(similarity_score=0.0, age_days=30)  # similarity=1.0, recency=0.5

    similarity_only = DefaultRankingStrategy(similarity_weight=1.0, recency_weight=0.0)
    recency_only = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0)

    assert similarity_only.score(candidate) == pytest.approx(1.0)
    assert recency_only.score(candidate) == pytest.approx(0.5, abs=1e-3)


def test_half_life_is_configurable():
    candidate = _candidate(age_days=10)
    short_half_life = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0, recency_half_life_days=5.0)
    long_half_life = DefaultRankingStrategy(similarity_weight=0.0, recency_weight=1.0, recency_half_life_days=500.0)

    # the same age decays further under a shorter half-life
    assert short_half_life.score(candidate) < long_half_life.score(candidate)


def test_default_weights_blend_both_components():
    strategy = DefaultRankingStrategy()
    candidate = _candidate(similarity_score=0.0, age_days=30)  # similarity=1.0, recency=0.5

    expected = strategy.similarity_weight * 1.0 + strategy.recency_weight * 0.5
    assert strategy.score(candidate) == pytest.approx(expected, abs=1e-3)


def test_default_weights_favor_similarity_over_recency():
    strategy = DefaultRankingStrategy()

    assert strategy.similarity_weight > strategy.recency_weight


def test_handles_naive_datetime_without_raising():
    strategy = DefaultRankingStrategy()
    candidate = RankingCandidate(
        resource_type="memory", resource_id=1, similarity_score=0.1, created_at=datetime(2024, 1, 1)
    )

    assert isinstance(strategy.score(candidate), float)
