"""PersonalIntelligencePolicy - domain-specific policy layered on top of
(never duplicating) SpecialistExecutionPolicy. See policies.py's own
docstring for why retry_policy/timeout_seconds are deliberately absent
here.
"""

import dataclasses

import pytest

from app.services.ai.agents.specialists.personal_intelligence.policies import PersonalIntelligencePolicy


def test_defaults():
    policy = PersonalIntelligencePolicy()
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = PersonalIntelligencePolicy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.minimum_confidence = 0.9


def test_custom_values_are_honored():
    policy = PersonalIntelligencePolicy(default_recall_limit=5, default_max_context_tokens=1000, minimum_confidence=0.5)
    assert policy.default_recall_limit == 5
    assert policy.default_max_context_tokens == 1000
    assert policy.minimum_confidence == 0.5


def test_does_not_duplicate_specialist_execution_policy_fields():
    # ResearchPolicy's own precedent: no retry_policy/timeout_seconds/
    # maximum_depth field here - those belong exclusively to
    # SpecialistExecutionPolicy.
    field_names = {f.name for f in dataclasses.fields(PersonalIntelligencePolicy)}
    assert field_names == {"default_recall_limit", "default_max_context_tokens", "minimum_confidence"}
    assert "retry_policy" not in field_names
    assert "timeout_seconds" not in field_names
    assert "maximum_depth" not in field_names
