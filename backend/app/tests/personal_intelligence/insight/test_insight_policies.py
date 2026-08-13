"""InsightPolicy - domain-specific policy layered on top of (never
duplicating) SpecialistExecutionPolicy.
"""

import dataclasses

import pytest

from app.services.ai.agents.specialists.personal_intelligence.insight.policies import InsightPolicy


def test_defaults():
    policy = InsightPolicy()
    assert policy.default_lookback_days == 30
    assert policy.default_maximum_memories_analyzed == 200
    assert policy.default_pattern_minimum_occurrences == 3
    assert policy.default_habit_minimum_occurrences == 2
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = InsightPolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.minimum_confidence = 0.9


def test_custom_values_are_honored():
    policy = InsightPolicy(default_lookback_days=7, default_pattern_minimum_occurrences=5, minimum_confidence=0.5)
    assert policy.default_lookback_days == 7
    assert policy.default_pattern_minimum_occurrences == 5
    assert policy.minimum_confidence == 0.5


def test_does_not_duplicate_specialist_execution_policy_fields():
    field_names = {f.name for f in dataclasses.fields(InsightPolicy)}
    assert "retry_policy" not in field_names
    assert "timeout_seconds" not in field_names
    assert "maximum_depth" not in field_names
